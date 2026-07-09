"""API contract tests for independent teacher onboarding — T-070."""

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
from app.features.independent_teacher_onboarding.models import IndependentTeacherProfile
from app.features.independent_users.models import (
    IndependentUser,
    IndependentUserAccountStatus,
    IndependentUserRole,
)


class _FakeProfileRepo:
    profiles: dict[str, IndependentTeacherProfile] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def get_by_user_id(self, user_id: str) -> IndependentTeacherProfile | None:
        return self.profiles.get(user_id)

    async def create(self, profile: IndependentTeacherProfile) -> IndependentTeacherProfile:
        now = datetime.now(timezone.utc)
        profile.created_at = now
        profile.updated_at = now
        self.profiles[profile.user_id] = profile
        return profile

    async def update(self, profile: IndependentTeacherProfile) -> IndependentTeacherProfile:
        self.profiles[profile.user_id] = profile
        return profile


class _FakeUserRepo:
    user: IndependentUser | None = None

    def __init__(self, session: Any) -> None:
        pass

    async def get_by_authentik_id(self, authentik_id: str) -> IndependentUser | None:
        if self.user and self.user.authentik_id == authentik_id:
            return self.user
        return None

    async def update(self, user: IndependentUser) -> IndependentUser:
        self.user = user
        return user


@pytest.fixture(autouse=True)
def _patch_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    _FakeProfileRepo.profiles = {}
    _FakeUserRepo.user = IndependentUser(
        authentik_id="auth-teacher-1",
        email="teacher@example.com",
        display_name="Teacher",
        role=IndependentUserRole.INDEPENDENT_TEACHER,
        status=IndependentUserAccountStatus.ACTIVE,
    )
    monkeypatch.setattr(
        "app.features.independent_teacher_onboarding.service.IndependentTeacherProfileRepository",
        _FakeProfileRepo,
    )
    monkeypatch.setattr(
        "app.features.independent_teacher_onboarding.service.IndependentUserRepository",
        _FakeUserRepo,
    )


async def _fake_db() -> AsyncGenerator[None, None]:
    yield None  # type: ignore[misc]


def _claims() -> dict[str, object]:
    return {"sub": "auth-teacher-1", "role": "independent_teacher", "tenant_type": "independent"}


def _build_client() -> AsyncClient:
    app = FastAPI()
    setup_exception_handlers(app)
    app.include_router(v1_router, prefix="/api/v1")
    app.dependency_overrides[get_db] = _fake_db
    app.dependency_overrides[get_current_user] = lambda: _claims()
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_get_onboarding_profile_incomplete() -> None:
    async with _build_client() as client:
        resp = await client.get("/api/v1/independent/teachers/me/onboarding")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["state"] == "profile_incomplete"
    assert data["ready_to_use"] is False


@pytest.mark.asyncio
async def test_complete_profile_reaches_ready_to_use() -> None:
    async with _build_client() as client:
        resp = await client.put(
            "/api/v1/independent/teachers/me/profile",
            json={"name": "Indie Teacher", "language_preference": "en"},
        )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["state"] == "ready_to_use"
    assert data["ready_to_use"] is True
    assert data["profile"]["name"] == "Indie Teacher"
