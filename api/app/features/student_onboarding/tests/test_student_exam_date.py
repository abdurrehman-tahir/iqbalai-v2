"""Exam date capture tests — T-083."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import date, datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.v1.router import router as v1_router
from app.core.dependencies import get_current_user, get_db
from app.core.exceptions import setup_exception_handlers
from app.features.student_onboarding.models import StudentProfile
from app.features.student_onboarding.service import (
    EXAM_COUNTDOWN_DAYS,
    StudentOnboardingService,
    derive_school_student_state,
)
from app.features.users.models import User, UserAccountStatus, UserRole


class _FakeProfileRepo:
    store: dict[str, StudentProfile] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def get_by_user_id(self, user_id: str) -> StudentProfile | None:
        return self.store.get(user_id)

    async def update(self, profile: StudentProfile) -> StudentProfile:
        self.store[profile.user_id] = profile
        return profile

    async def list_with_exam_dates(self) -> list[StudentProfile]:
        return [p for p in self.store.values() if p.exam_date is not None]


class _FakeUserRepo:
    store: dict[str, User] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def get_by_authentik_id(self, authentik_id: str) -> User | None:
        return next((u for u in self.store.values() if u.authentik_id == authentik_id), None)

    async def get_by_id(self, user_id: str) -> User | None:
        return self.store.get(user_id)


STUDENT = User(
    id="student-1",
    authentik_id="auth-student",
    email="student@example.com",
    display_name="Student One",
    role=UserRole.STUDENT,
    status=UserAccountStatus.ACTIVE,
    school_id="school-1",
)

READY_PROFILE = StudentProfile(
    user_id=STUDENT.id,
    display_name="Student One",
    language_preference="en",
    tos_accepted_at=datetime.now(timezone.utc),
    profile_basic_completed_at=datetime.now(timezone.utc),
    lecture_mode_enabled=True,
    self_study_mode_enabled=False,
)


@pytest.fixture(autouse=True)
def _patch_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    _FakeProfileRepo.store = {STUDENT.id: READY_PROFILE}
    _FakeUserRepo.store = {STUDENT.id: STUDENT}
    monkeypatch.setattr(
        "app.features.student_onboarding.service.StudentProfileRepository", _FakeProfileRepo
    )
    monkeypatch.setattr("app.features.student_onboarding.service.UserRepository", _FakeUserRepo)
    monkeypatch.setattr("app.features.student_onboarding.service.audit", AsyncMock())
    monkeypatch.setattr(
        "app.features.student_onboarding.service.StudentOnboardingService._active_enrollment_grade_id",
        AsyncMock(return_value="grade-9"),
    )


async def _fake_db() -> AsyncGenerator[None, None]:
    yield None  # type: ignore[misc]


def _build_client() -> AsyncClient:
    app = FastAPI()
    setup_exception_handlers(app)
    app.include_router(v1_router, prefix="/api/v1")
    app.dependency_overrides[get_db] = _fake_db
    app.dependency_overrides[get_current_user] = lambda: {
        "sub": STUDENT.authentik_id,
        "user_id": STUDENT.id,
        "role": STUDENT.role.value,
        "tenant_type": "school",
        "school_id": STUDENT.school_id,
    }
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_set_exam_date_persists() -> None:
    future = (date.today() + timedelta(days=60)).isoformat()
    async with _build_client() as client:
        resp = await client.put(
            "/api/v1/students/me/onboarding/exam-date", json={"exam_date": future}
        )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["exam_date_set"] is True
    assert data["show_complete_profile_banner"] is False
    assert _FakeProfileRepo.store[STUDENT.id].exam_date == date.fromisoformat(future)


@pytest.mark.asyncio
async def test_set_exam_date_rejects_past_date() -> None:
    past = (date.today() - timedelta(days=1)).isoformat()
    async with _build_client() as client:
        resp = await client.put(
            "/api/v1/students/me/onboarding/exam-date", json={"exam_date": past}
        )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_update_exam_date_is_editable() -> None:
    first = (date.today() + timedelta(days=30)).isoformat()
    second = (date.today() + timedelta(days=45)).isoformat()
    async with _build_client() as client:
        await client.put("/api/v1/students/me/onboarding/exam-date", json={"exam_date": first})
        resp = await client.put(
            "/api/v1/students/me/onboarding/exam-date", json={"exam_date": second}
        )
    assert resp.status_code == 200
    assert _FakeProfileRepo.store[STUDENT.id].exam_date == date.fromisoformat(second)
    assert _FakeProfileRepo.store[STUDENT.id].exam_countdown_sent_days is None


def test_banner_hidden_when_exam_date_set() -> None:
    profile = StudentProfile(
        user_id=STUDENT.id,
        display_name="Student One",
        language_preference="en",
        tos_accepted_at=datetime.now(timezone.utc),
        profile_basic_completed_at=datetime.now(timezone.utc),
        lecture_mode_enabled=True,
        self_study_mode_enabled=False,
        exam_date=date.today() + timedelta(days=30),
    )
    state = derive_school_student_state(
        user=STUDENT, profile=profile, enrollment_grade_id="grade-9"
    )
    assert state.exam_date_set
    assert not state.show_complete_profile_banner


@pytest.mark.asyncio
async def test_exam_countdown_notifications_for_registered_days(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profile = _FakeProfileRepo.store[STUDENT.id]
    profile.exam_date = date.today() + timedelta(days=30)
    profile.exam_countdown_sent_days = None

    notify_mock = AsyncMock()
    monkeypatch.setattr(
        "app.infrastructure.notifications.self_study.notify_self_study_event",
        notify_mock,
    )

    svc = StudentOnboardingService(AsyncMock())
    count = await svc.send_exam_countdown_notifications()

    assert count == 1
    notify_mock.assert_called_once()
    assert profile.exam_countdown_sent_days == "30"
    assert 30 in EXAM_COUNTDOWN_DAYS
