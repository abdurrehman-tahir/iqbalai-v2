"""API contract tests for parent signup — T-080."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.v1.router import router as v1_router
from app.core.dependencies import get_db
from app.core.exceptions import setup_exception_handlers
from app.features.parent_signup.models import ParentProfile
from app.features.users.models import User, UserAccountStatus, UserRole
from app.infrastructure.authentik.client import DevAuthentikClient


class _FakeUserRepo:
    store: dict[str, User] = {}
    by_email: dict[str, User] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def get_by_email(self, email: str) -> User | None:
        return self.by_email.get(email.lower())

    async def get_by_authentik_id(self, authentik_id: str) -> User | None:
        return next((u for u in self.store.values() if u.authentik_id == authentik_id), None)

    async def create(self, user: User) -> User:
        now = datetime.now(timezone.utc)
        user.created_at = now
        user.updated_at = now
        self.store[user.id] = user
        self.by_email[user.email.lower()] = user
        return user

    async def update(self, user: User) -> User:
        self.store[user.id] = user
        return user


class _FakeParentProfileRepo:
    store: dict[str, ParentProfile] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def get_by_user_id(self, user_id: str) -> ParentProfile | None:
        return self.store.get(user_id)

    async def create(self, profile: ParentProfile) -> ParentProfile:
        now = datetime.now(timezone.utc)
        profile.created_at = now
        profile.updated_at = now
        self.store[profile.user_id] = profile
        return profile

    async def update(self, profile: ParentProfile) -> ParentProfile:
        self.store[profile.user_id] = profile
        return profile

    async def list_stale_unlinked(self, cutoff: datetime) -> list[tuple[User, ParentProfile]]:
        stale: list[tuple[User, ParentProfile]] = []
        for user in _FakeUserRepo.store.values():
            profile = self.store.get(user.id)
            if (
                profile is not None
                and user.role == UserRole.PARENT
                and user.status == UserAccountStatus.ACTIVE
                and profile.is_email_verified
                and profile.unlinked_since is not None
                and profile.unlinked_since <= cutoff
            ):
                stale.append((user, profile))
        return stale


class _FakeIndependentUserRepo:
    def __init__(self, session: Any) -> None:
        pass

    async def get_by_email(self, email: str) -> object | None:
        return None


@pytest.fixture(autouse=True)
def _patch_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    _FakeUserRepo.store = {}
    _FakeUserRepo.by_email = {}
    _FakeParentProfileRepo.store = {}
    monkeypatch.setattr("app.features.parent_signup.service.UserRepository", _FakeUserRepo)
    monkeypatch.setattr("app.features.parent_signup.service.ParentProfileRepository", _FakeParentProfileRepo)
    monkeypatch.setattr(
        "app.features.parent_signup.service.IndependentUserRepository",
        _FakeIndependentUserRepo,
    )
    monkeypatch.setattr("app.features.parent_signup.service.audit", AsyncMock())
    monkeypatch.setattr("app.features.parent_signup.service.send_account_email", AsyncMock())
    monkeypatch.setattr(
        "app.features.parent_signup.service.get_authentik_client",
        lambda: DevAuthentikClient(),
    )


async def _fake_db() -> AsyncGenerator[None, None]:
    yield None  # type: ignore[misc]


def _build_client() -> AsyncClient:
    app = FastAPI()
    setup_exception_handlers(app)
    app.include_router(v1_router, prefix="/api/v1")
    app.dependency_overrides[get_db] = _fake_db
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_get_parent_signup_info() -> None:
    async with _build_client() as client:
        resp = await client.get("/api/v1/parents/signup")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "en" in data["languages"]


@pytest.mark.asyncio
async def test_post_parent_signup_creates_school_parent_user() -> None:
    async with _build_client() as client:
        resp = await client.post(
            "/api/v1/parents/signup",
            json={
                "email": "parent@example.com",
                "password": "securepass1",
                "display_name": "Parent One",
                "language_preference": "en",
            },
        )
    assert resp.status_code == 201
    body = resp.json()["data"]
    assert body["email"] == "parent@example.com"
    assert body["role"] == "parent"
    assert body["tenant_type"] == "school"
    assert body["parent_state"] == "PARENT_REGISTERED"
    assert len(_FakeUserRepo.store) == 1
    user = next(iter(_FakeUserRepo.store.values()))
    assert user.role == UserRole.PARENT
    assert user.school_id is None
    assert user.district_id is None
    profile = _FakeParentProfileRepo.store[user.id]
    assert profile.is_email_verified is False
    assert profile.unlinked_since is None


@pytest.mark.asyncio
async def test_post_parent_signup_rejects_duplicate_email() -> None:
    existing = User(
        authentik_id="existing-id",
        email="dup@example.com",
        display_name="Existing",
        role=UserRole.PARENT,
        status=UserAccountStatus.ACTIVE,
    )
    _FakeUserRepo.store[existing.id] = existing
    _FakeUserRepo.by_email[existing.email] = existing

    async with _build_client() as client:
        resp = await client.post(
            "/api/v1/parents/signup",
            json={
                "email": "dup@example.com",
                "password": "securepass1",
                "display_name": "Another",
                "language_preference": "ur",
            },
        )
    assert resp.status_code == 409
