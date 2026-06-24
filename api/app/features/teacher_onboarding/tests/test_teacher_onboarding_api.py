"""API contract tests for teacher onboarding — T-053."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.v1.router import router as v1_router
from app.core.dependencies import get_current_user, get_db
from app.core.exceptions import setup_exception_handlers
from app.features.subjects.models import Subject, SubjectStatus
from app.features.teacher_onboarding.models import TeacherProfile
from app.features.teacher_onboarding.service import derive_onboarding_state
from app.features.users.models import User, UserAccountStatus, UserRole


class _FakeProfileRepo:
    profiles: dict[str, TeacherProfile] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def get_by_user_id(self, user_id: str) -> TeacherProfile | None:
        profile = self.profiles.get(user_id)
        if profile is not None and profile.deleted_at is not None:
            return None
        return profile

    async def create(self, profile: TeacherProfile) -> TeacherProfile:
        now = datetime.now(timezone.utc)
        profile.created_at = now
        profile.updated_at = now
        self.profiles[profile.user_id] = profile
        return profile

    async def update(self, profile: TeacherProfile) -> TeacherProfile:
        self.profiles[profile.user_id] = profile
        return profile


class _FakeUserRepo:
    users: dict[str, User] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def get_by_authentik_id(self, authentik_id: str) -> User | None:
        return self.users.get(authentik_id)

    async def update(self, user: User) -> User:
        self.users[user.authentik_id] = user
        return user

    async def list_by_school_and_role(self, school_id: str, role: UserRole) -> list[User]:
        return [
            user
            for user in self.users.values()
            if user.school_id == school_id and user.role == role and user.deleted_at is None
        ]


class _FakeOfferingRepo:
    assignment_counts: dict[str, int] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def count_active_assignments_for_teacher(self, teacher_id: str) -> int:
        return _FakeOfferingRepo.assignment_counts.get(teacher_id, 0)


class _FakeSubjectRepo:
    subjects: list[Subject] = []

    def __init__(self, session: Any) -> None:
        pass

    async def list_by_school(self, school_id: str, include_archived: bool = False) -> list[Subject]:
        rows = [
            s
            for s in self.subjects
            if s.school_id == school_id
            and s.deleted_at is None
            and s.status == SubjectStatus.ACTIVE
        ]
        return rows


def _teacher(**overrides: object) -> User:
    base = User(
        id="teacher-1",
        authentik_id="teacher-1",
        email="teacher@test.com",
        display_name="Teacher",
        role=UserRole.TEACHER,
        status=UserAccountStatus.ACTIVE,
        school_id="school-1",
    )
    for key, value in overrides.items():
        setattr(base, key, value)
    return base


@pytest.fixture(autouse=True)
def _patch_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    _FakeProfileRepo.profiles = {}
    _FakeUserRepo.users = {"teacher-1": _teacher()}
    _FakeOfferingRepo.assignment_counts = {"teacher-1": 0}
    _FakeSubjectRepo.subjects = [
        Subject(
            id="subj-1",
            school_id="school-1",
            name="Physics",
            language="en",
            status=SubjectStatus.ACTIVE,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
    ]
    monkeypatch.setattr(
        "app.features.teacher_onboarding.service.TeacherProfileRepository",
        _FakeProfileRepo,
    )
    monkeypatch.setattr(
        "app.features.teacher_onboarding.service.UserRepository",
        _FakeUserRepo,
    )
    monkeypatch.setattr(
        "app.features.teacher_onboarding.service.OfferingRepository",
        _FakeOfferingRepo,
    )
    monkeypatch.setattr(
        "app.features.teacher_onboarding.service.SubjectRepository",
        _FakeSubjectRepo,
    )


def _build_client() -> AsyncClient:
    app = FastAPI()
    app.include_router(v1_router, prefix="/api/v1")
    setup_exception_handlers(app)

    async def _override_db() -> AsyncGenerator[None, None]:
        yield None

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = lambda: {
        "sub": "teacher-1",
        "role": "teacher",
        "school_id": "school-1",
    }
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_onboarding_profile_incomplete_by_default() -> None:
    async with _build_client() as client:
        resp = await client.get("/api/v1/teachers/me/onboarding")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["state"] == "profile_incomplete"
    assert data["profile_complete"] is False
    assert data["ready_to_teach"] is False
    assert data["assignment_count"] == 0


@pytest.mark.asyncio
async def test_complete_profile_then_profile_complete_without_assignments() -> None:
    async with _build_client() as client:
        resp = await client.put(
            "/api/v1/teachers/me/profile",
            json={
                "name": "Ali Khan",
                "region_province": "Punjab",
                "region_district": "Lahore",
                "bio": "Physics teacher",
                "language_preference": "en",
                "subject_ids": ["subj-1"],
            },
        )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["state"] == "profile_complete"
    assert data["profile_complete"] is True
    assert data["ready_to_teach"] is False
    assert data["profile"]["name"] == "Ali Khan"


@pytest.mark.asyncio
async def test_ready_to_teach_when_assigned() -> None:
    _FakeOfferingRepo.assignment_counts["teacher-1"] = 1
    _FakeProfileRepo.profiles["teacher-1"] = TeacherProfile(
        user_id="teacher-1",
        name="Ali Khan",
        region_province="Punjab",
        region_district=None,
        bio=None,
        language_preference="en",
        subject_ids=["subj-1"],
        profile_completed_at=datetime.now(timezone.utc),
    )
    async with _build_client() as client:
        resp = await client.get("/api/v1/teachers/me/onboarding")
    data = resp.json()["data"]
    assert data["state"] == "ready_to_teach"
    assert data["ready_to_teach"] is True
    assert data["can_create_content"] is True


@pytest.mark.asyncio
async def test_suspended_teacher_blocked_from_profile_completion() -> None:
    _FakeUserRepo.users["teacher-1"] = _teacher(status=UserAccountStatus.SUSPENDED)
    async with _build_client() as client:
        resp = await client.put(
            "/api/v1/teachers/me/profile",
            json={
                "name": "Ali Khan",
                "region_province": "Punjab",
                "language_preference": "en",
                "subject_ids": ["subj-1"],
            },
        )
    assert resp.status_code == 403


def test_derive_onboarding_state_is_computed_not_stored() -> None:
    profile = TeacherProfile(
        user_id="teacher-1",
        name="Ali",
        region_province="Punjab",
        region_district=None,
        bio=None,
        language_preference="en",
        subject_ids=["subj-1"],
        profile_completed_at=datetime.now(timezone.utc),
    )
    without_assignments = derive_onboarding_state(
        profile=profile,
        assignment_count=0,
        account_status=UserAccountStatus.ACTIVE,
    )
    with_assignments = derive_onboarding_state(
        profile=profile,
        assignment_count=1,
        account_status=UserAccountStatus.ACTIVE,
    )
    assert without_assignments.ready_to_teach is False
    assert with_assignments.ready_to_teach is True

    suspended = derive_onboarding_state(
        profile=profile,
        assignment_count=1,
        account_status=UserAccountStatus.SUSPENDED,
    )
    assert suspended.ready_to_teach is True
    assert suspended.can_create_content is False


@pytest.mark.asyncio
async def test_list_subject_options_for_teacher() -> None:
    async with _build_client() as client:
        resp = await client.get("/api/v1/teachers/me/subject-options")
    assert resp.status_code == 200
    items = resp.json()["data"]
    assert len(items) == 1
    assert items[0]["name"] == "Physics"


@pytest.mark.asyncio
async def test_update_capacity_within_bounds(monkeypatch: pytest.MonkeyPatch) -> None:
    audit_calls: list[dict[str, object]] = []
    notify_calls: list[str] = []

    async def _fake_audit(**kwargs: object) -> None:
        audit_calls.append(kwargs)

    async def _fake_notify(**kwargs: object) -> None:
        notify_calls.append(str(kwargs.get("template_key")))

    monkeypatch.setattr("app.features.teacher_onboarding.service.audit", _fake_audit)
    monkeypatch.setattr(
        "app.features.teacher_onboarding.service.notify_account_event",
        _fake_notify,
    )

    async with _build_client() as client:
        resp = await client.patch(
            "/api/v1/teachers/me/capacity",
            json={"teacher_capacity": 8},
        )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["teacher_capacity"] == 8
    assert data["assignment_count"] == 0
    assert data["capacity_below_assignments"] is False
    assert _FakeUserRepo.users["teacher-1"].teacher_capacity == 8
    assert audit_calls[0]["action"] == "capacity.updated"
    assert notify_calls.count("account.capacity_changed") >= 1


@pytest.mark.asyncio
async def test_update_capacity_rejects_out_of_range() -> None:
    async with _build_client() as client:
        resp = await client.patch(
            "/api/v1/teachers/me/capacity",
            json={"teacher_capacity": 25},
        )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_update_capacity_below_assignments_flagged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _FakeOfferingRepo.assignment_counts["teacher-1"] = 6
    _FakeUserRepo.users["teacher-1"] = _teacher(teacher_capacity=8)

    async def _fake_audit(**kwargs: object) -> None:
        pass

    async def _fake_notify(**kwargs: object) -> None:
        pass

    monkeypatch.setattr("app.features.teacher_onboarding.service.audit", _fake_audit)
    monkeypatch.setattr(
        "app.features.teacher_onboarding.service.notify_account_event",
        _fake_notify,
    )

    async with _build_client() as client:
        resp = await client.patch(
            "/api/v1/teachers/me/capacity",
            json={"teacher_capacity": 4},
        )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["teacher_capacity"] == 4
    assert data["assignment_count"] == 6
    assert data["capacity_below_assignments"] is True


@pytest.mark.asyncio
async def test_onboarding_includes_capacity_fields() -> None:
    _FakeUserRepo.users["teacher-1"] = _teacher(teacher_capacity=7)
    _FakeOfferingRepo.assignment_counts["teacher-1"] = 3
    async with _build_client() as client:
        resp = await client.get("/api/v1/teachers/me/onboarding")
    data = resp.json()["data"]
    assert data["teacher_capacity"] == 7
    assert data["capacity_below_assignments"] is False
