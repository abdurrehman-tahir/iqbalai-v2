"""T-162 — #72 teacher-activity privacy: default-share, opt-out audit, parent filter."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.dependencies import get_current_user, get_db
from app.core.exceptions import setup_exception_handlers
from app.features.audit.actions import STUDENT_TEACHER_SHARE_TOGGLED
from app.features.student_mode.models import StudyMode, TeacherActivityShare, UserSettings
from app.features.student_onboarding.models import StudentProfile
from app.features.student_privacy.parent_router import router as parent_lecture_questions_router
from app.features.student_privacy.router import router as student_privacy_router
from app.features.student_privacy.service import student_allows_teacher_share
from app.features.users.models import User, UserAccountStatus, UserRole


class _FakeSettingsRepo:
    store: dict[str, UserSettings] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def get_by_user_id(self, user_id: str) -> UserSettings | None:
        return self.store.get(user_id)

    async def create(self, settings: UserSettings) -> UserSettings:
        self.store[settings.user_id] = settings
        return settings

    async def update(self, settings: UserSettings) -> UserSettings:
        self.store[settings.user_id] = settings
        return settings


class _FakeProfileRepo:
    store: dict[str, StudentProfile] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def get_by_user_id(self, user_id: str) -> StudentProfile | None:
        return self.store.get(user_id)


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


@pytest.fixture(autouse=True)
def _patch_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime.now(timezone.utc)
    profile = StudentProfile(
        user_id=STUDENT.id,
        display_name="Student One",
        language_preference="en",
        tos_accepted_at=now,
        profile_basic_completed_at=now,
        lecture_mode_enabled=True,
        self_study_mode_enabled=True,
    )
    _FakeSettingsRepo.store = {}
    _FakeProfileRepo.store = {STUDENT.id: profile}
    _FakeUserRepo.store = {STUDENT.id: STUDENT}

    monkeypatch.setattr(
        "app.features.student_privacy.service.UserSettingsRepository", _FakeSettingsRepo
    )
    monkeypatch.setattr(
        "app.features.student_privacy.service.StudentProfileRepository", _FakeProfileRepo
    )
    monkeypatch.setattr("app.features.student_privacy.service.UserRepository", _FakeUserRepo)
    monkeypatch.setattr("app.features.student_privacy.service.audit", AsyncMock())


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    app = FastAPI()
    setup_exception_handlers(app)
    app.include_router(student_privacy_router, prefix="/api/v1")
    app.include_router(parent_lecture_questions_router, prefix="/api/v1")

    async def _claims() -> dict[str, object]:
        return {
            "sub": STUDENT.authentik_id,
            "role": "student",
            "tenant_type": "school",
            "school_id": "school-1",
        }

    async def _db() -> AsyncGenerator[Any, None]:
        yield object()

    app.dependency_overrides[get_current_user] = _claims
    app.dependency_overrides[get_db] = _db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_default_share_when_no_settings_row(client: AsyncClient) -> None:
    """Open Q12 — missing user_settings ⇒ share."""
    res = await client.get("/api/v1/students/me/privacy/teacher-share")
    assert res.status_code == 200
    body = res.json()["data"]
    assert body["teacher_activity_share"] == "share"
    assert _FakeSettingsRepo.store[STUDENT.id].teacher_activity_share == TeacherActivityShare.SHARE


@pytest.mark.asyncio
async def test_opt_out_is_audit_logged(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    audit_mock = AsyncMock()
    monkeypatch.setattr("app.features.student_privacy.service.audit", audit_mock)

    res = await client.patch(
        "/api/v1/students/me/privacy/teacher-share",
        json={"teacher_activity_share": "private"},
    )
    assert res.status_code == 200
    assert res.json()["data"]["teacher_activity_share"] == "private"
    assert (
        _FakeSettingsRepo.store[STUDENT.id].teacher_activity_share == TeacherActivityShare.PRIVATE
    )

    audit_mock.assert_awaited_once()
    kwargs = audit_mock.await_args.kwargs
    assert kwargs["action"] == STUDENT_TEACHER_SHARE_TOGGLED
    assert kwargs["target_type"] == "user_settings"
    assert kwargs["target_id"] == STUDENT.id
    assert kwargs["metadata"]["teacher_activity_share"] == "private"
    assert kwargs["metadata"]["previous"] == "share"
    assert kwargs["metadata"]["feature"] == "72"


@pytest.mark.asyncio
async def test_student_allows_teacher_share_helper_defaults_and_opt_out() -> None:
    """Parent / event consumers use the shared helper."""
    session = object()

    _FakeSettingsRepo.store = {}
    assert await student_allows_teacher_share(session, STUDENT.id) is True  # type: ignore[arg-type]

    _FakeSettingsRepo.store[STUDENT.id] = UserSettings(
        user_id=STUDENT.id,
        active_mode=StudyMode.LECTURE,
        teacher_activity_share=TeacherActivityShare.SHARE,
    )
    assert await student_allows_teacher_share(session, STUDENT.id) is True  # type: ignore[arg-type]

    _FakeSettingsRepo.store[STUDENT.id].teacher_activity_share = TeacherActivityShare.PRIVATE
    assert await student_allows_teacher_share(session, STUDENT.id) is False  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_independent_student_gets_404() -> None:
    app = FastAPI()
    setup_exception_handlers(app)
    app.include_router(student_privacy_router, prefix="/api/v1")

    async def _claims() -> dict[str, object]:
        return {"sub": "indie", "role": "independent_student", "tenant_type": "independent"}

    async def _db() -> AsyncGenerator[Any, None]:
        yield object()

    app.dependency_overrides[get_current_user] = _claims
    app.dependency_overrides[get_db] = _db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/api/v1/students/me/privacy/teacher-share")
    assert res.status_code == 404
