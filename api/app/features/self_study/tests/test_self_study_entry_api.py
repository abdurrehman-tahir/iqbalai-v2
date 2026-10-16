"""T-209 — self-study entry + state persistence API contract tests."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.v1.router import router as v1_router
from app.core.dependencies import get_current_user, get_db
from app.core.exceptions import setup_exception_handlers
from app.features.independent_users.models import (
    IndependentUser,
    IndependentUserAccountStatus,
    IndependentUserRole,
)
from app.features.self_study.models import IndependentUserSettings
from app.features.student_mode.models import StudyMode, UserSettings
from app.features.users.models import User, UserAccountStatus, UserRole


class _FakeSchoolSettingsRepo:
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


class _FakeIndSettingsRepo:
    store: dict[str, IndependentUserSettings] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def get_by_user_id(self, user_id: str) -> IndependentUserSettings | None:
        return self.store.get(user_id)

    async def create(self, settings: IndependentUserSettings) -> IndependentUserSettings:
        self.store[settings.user_id] = settings
        return settings

    async def update(self, settings: IndependentUserSettings) -> IndependentUserSettings:
        self.store[settings.user_id] = settings
        return settings


class _FakeSchoolUserRepo:
    store: dict[str, User] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def get_by_authentik_id(self, authentik_id: str) -> User | None:
        return next((u for u in self.store.values() if u.authentik_id == authentik_id), None)


class _FakeIndUserRepo:
    store: dict[str, IndependentUser] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def get_by_authentik_id(self, authentik_id: str) -> IndependentUser | None:
        return next((u for u in self.store.values() if u.authentik_id == authentik_id), None)


SCHOOL_STUDENT = User(
    id="school-u1",
    authentik_id="auth-school-1",
    email="s@example.com",
    display_name="School Student",
    role=UserRole.STUDENT,
    status=UserAccountStatus.ACTIVE,
    school_id="school-1",
)

IND_STUDENT = IndependentUser(
    id="ind-u1",
    authentik_id="auth-ind-1",
    email="i@example.com",
    display_name="Ind Student",
    role=IndependentUserRole.INDEPENDENT_STUDENT,
    status=IndependentUserAccountStatus.ACTIVE,
)


@pytest.fixture(autouse=True)
def _patch_repos(monkeypatch: pytest.MonkeyPatch) -> None:
    _FakeSchoolSettingsRepo.store = {
        SCHOOL_STUDENT.id: UserSettings(
            user_id=SCHOOL_STUDENT.id,
            active_mode=StudyMode.SELF_STUDY,
            mode_state_jsonb={
                "lecture": {},
                "self_study": {"last_goal_id": "goal-1", "last_material_id": "mat-1"},
            },
        )
    }
    _FakeIndSettingsRepo.store = {
        IND_STUDENT.id: IndependentUserSettings(
            user_id=IND_STUDENT.id,
            mode_state_jsonb={"self_study": {"last_plan_view": "calendar"}},
        )
    }
    _FakeSchoolUserRepo.store = {SCHOOL_STUDENT.id: SCHOOL_STUDENT}
    _FakeIndUserRepo.store = {IND_STUDENT.id: IND_STUDENT}
    monkeypatch.setattr(
        "app.features.self_study.service.UserSettingsRepository",
        _FakeSchoolSettingsRepo,
    )
    monkeypatch.setattr(
        "app.features.self_study.service.IndependentUserSettingsRepository",
        _FakeIndSettingsRepo,
    )
    monkeypatch.setattr(
        "app.features.self_study.service.UserRepository",
        _FakeSchoolUserRepo,
    )
    monkeypatch.setattr(
        "app.features.self_study.service.IndependentUserRepository",
        _FakeIndUserRepo,
    )


async def _fake_db() -> AsyncGenerator[None, None]:
    yield None


def _make_app(claims: dict[str, object]) -> FastAPI:
    application = FastAPI()
    setup_exception_handlers(application)
    application.include_router(v1_router, prefix="/api/v1")
    application.dependency_overrides[get_db] = _fake_db
    application.dependency_overrides[get_current_user] = lambda: claims
    return application


@pytest.mark.asyncio
async def test_school_entry_resumes_self_study_state() -> None:
    app = _make_app({"sub": "auth-school-1", "role": "student", "tenant_type": "school"})
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/self-study/me/entry")
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["tenant_type"] == "school"
    assert body["locked_to_self_study"] is False
    assert body["active_mode"] == "self_study"
    assert body["state"]["last_goal_id"] == "goal-1"
    assert body["state"]["last_material_id"] == "mat-1"
    assert body["subscription_gate"]["enforced"] is False
    assert body["lecture_mode_redirect_to"] is None


@pytest.mark.asyncio
async def test_independent_entry_locked_and_redirect() -> None:
    app = _make_app(
        {
            "sub": "auth-ind-1",
            "role": "independent_student",
            "tenant_type": "independent",
        }
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/self-study/me/entry")
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["tenant_type"] == "independent"
    assert body["locked_to_self_study"] is True
    assert body["active_mode"] == "self_study"
    assert body["state"]["last_plan_view"] == "calendar"
    assert body["lecture_mode_redirect_to"] == "/independent/student"


@pytest.mark.asyncio
async def test_patch_state_school() -> None:
    app = _make_app({"sub": "auth-school-1", "role": "student", "tenant_type": "school"})
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.patch(
            "/api/v1/self-study/me/state",
            json={"last_goal_id": "g-9", "last_plan_view": "week"},
        )
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["state"]["last_goal_id"] == "g-9"
    assert body["state"]["last_plan_view"] == "week"
    stored = _FakeSchoolSettingsRepo.store[SCHOOL_STUDENT.id]
    self_study_blob = stored.mode_state_jsonb["self_study"]
    assert isinstance(self_study_blob, dict)
    assert self_study_blob["last_goal_id"] == "g-9"
