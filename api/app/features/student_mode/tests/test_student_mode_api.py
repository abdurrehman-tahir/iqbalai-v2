"""Mode Switcher API tests — T-101."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.v1.router import router as v1_router
from app.core.dependencies import get_current_user, get_db
from app.core.exceptions import setup_exception_handlers
from app.features.student_mode.models import StudyMode, UserSettings
from app.features.student_onboarding.models import StudentProfile
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

    async def update(self, profile: StudentProfile) -> StudentProfile:
        self.store[profile.user_id] = profile
        return profile


class _FakeUserRepo:
    store: dict[str, User] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def get_by_authentik_id(self, authentik_id: str) -> User | None:
        return next((u for u in self.store.values() if u.authentik_id == authentik_id), None)


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
    profile = StudentProfile(
        user_id=STUDENT.id,
        display_name="Student One",
        language_preference="en",
        tos_accepted_at=datetime.now(timezone.utc),
        profile_basic_completed_at=datetime.now(timezone.utc),
        lecture_mode_enabled=True,
        self_study_mode_enabled=True,
    )
    _FakeSettingsRepo.store = {}
    _FakeProfileRepo.store = {STUDENT.id: profile}
    _FakeUserRepo.store = {STUDENT.id: STUDENT}
    monkeypatch.setattr(
        "app.features.student_mode.service.UserSettingsRepository", _FakeSettingsRepo
    )
    monkeypatch.setattr(
        "app.features.student_mode.service.StudentProfileRepository", _FakeProfileRepo
    )
    monkeypatch.setattr("app.features.student_mode.service.UserRepository", _FakeUserRepo)
    monkeypatch.setattr("app.features.student_mode.service.audit", AsyncMock())
    monkeypatch.setattr("app.features.student_mode.service.publish_mode_changed", AsyncMock())


async def _fake_db() -> AsyncGenerator[None, None]:
    yield None


def _build_client(claims: dict[str, object]) -> AsyncClient:
    app = FastAPI()
    setup_exception_handlers(app)
    app.include_router(v1_router, prefix="/api/v1")
    app.dependency_overrides[get_db] = _fake_db
    app.dependency_overrides[get_current_user] = lambda: claims
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_get_mode_creates_settings_with_lecture_default() -> None:
    async with _build_client(
        {"sub": "auth-student", "role": "student", "tenant_type": "school"}
    ) as client:
        res = await client.get("/api/v1/students/me/mode")
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["active_mode"] == "lecture"
    assert data["mode_state"] == {"lecture": {}, "self_study": {}}
    assert STUDENT.id in _FakeSettingsRepo.store


@pytest.mark.asyncio
async def test_put_mode_switches_and_preserves_leaving_state() -> None:
    _FakeSettingsRepo.store[STUDENT.id] = UserSettings(
        user_id=STUDENT.id,
        active_mode=StudyMode.LECTURE,
        mode_state_jsonb={"lecture": {}, "self_study": {}},
    )
    async with _build_client(
        {"sub": "auth-student", "role": "student", "tenant_type": "school"}
    ) as client:
        res = await client.put(
            "/api/v1/students/me/mode",
            json={
                "active_mode": "self_study",
                "leaving_mode_state": {"scroll_y": 120, "section": "lectures"},
            },
        )
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["active_mode"] == "self_study"
    assert data["mode_state"]["lecture"] == {"scroll_y": 120, "section": "lectures"}
    assert data["mode_state"]["self_study"] == {}


@pytest.mark.asyncio
async def test_independent_student_mode_returns_404() -> None:
    async with _build_client(
        {
            "sub": "auth-indie",
            "role": "independent_student",
            "tenant_type": "independent",
        }
    ) as client:
        get_res = await client.get("/api/v1/students/me/mode")
        put_res = await client.put(
            "/api/v1/students/me/mode",
            json={"active_mode": "lecture"},
        )
    assert get_res.status_code == 404
    assert put_res.status_code == 404
