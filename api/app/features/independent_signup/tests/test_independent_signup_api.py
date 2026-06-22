"""API contract tests for independent signup — T-069."""

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
from app.features.independent_users.models import (
    IndependentUser,
    IndependentUserAccountStatus,
    IndependentUserRole,
)
from app.infrastructure.authentik.client import DevAuthentikClient


class _FakeIndependentUserRepo:
    store: dict[str, IndependentUser] = {}
    by_email: dict[str, IndependentUser] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def get_by_email(self, email: str) -> IndependentUser | None:
        return self.by_email.get(email.lower())

    async def get_by_authentik_id(self, authentik_id: str) -> IndependentUser | None:
        return next((u for u in self.store.values() if u.authentik_id == authentik_id), None)

    async def create(self, user: IndependentUser) -> IndependentUser:
        now = datetime.now(timezone.utc)
        user.created_at = now
        user.updated_at = now
        self.store[user.id] = user
        self.by_email[user.email.lower()] = user
        return user

    async def update(self, user: IndependentUser) -> IndependentUser:
        self.store[user.id] = user
        return user


class _FakeSchoolUserRepo:
    def __init__(self, session: Any) -> None:
        pass

    async def get_by_email(self, email: str) -> object | None:
        return None


@pytest.fixture(autouse=True)
def _patch_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    _FakeIndependentUserRepo.store = {}
    _FakeIndependentUserRepo.by_email = {}
    monkeypatch.setattr(
        "app.features.independent_signup.service.IndependentUserRepository",
        _FakeIndependentUserRepo,
    )
    monkeypatch.setattr(
        "app.features.independent_signup.service.UserRepository",
        _FakeSchoolUserRepo,
    )
    monkeypatch.setattr("app.features.independent_signup.service.audit", AsyncMock())
    monkeypatch.setattr("app.features.independent_signup.service.send_account_email", AsyncMock())
    monkeypatch.setattr(
        "app.features.independent_signup.service.get_authentik_client",
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
async def test_get_independent_signup_info() -> None:
    async with _build_client() as client:
        resp = await client.get("/api/v1/independent/signup")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "independent_teacher" in data["roles"]
    assert "independent_student" in data["roles"]
    assert "en" in data["languages"]


@pytest.mark.asyncio
async def test_post_independent_signup_creates_user_in_independent_schema() -> None:
    async with _build_client() as client:
        resp = await client.post(
            "/api/v1/independent/signup",
            json={
                "email": "teacher@example.com",
                "password": "securepass1",
                "display_name": "Indie Teacher",
                "role": "independent_teacher",
                "language_preference": "en",
            },
        )
    assert resp.status_code == 201
    body = resp.json()["data"]
    assert body["email"] == "teacher@example.com"
    assert body["role"] == "independent_teacher"
    assert body["tenant_type"] == "independent"
    assert len(_FakeIndependentUserRepo.store) == 1
    user = next(iter(_FakeIndependentUserRepo.store.values()))
    assert user.role == IndependentUserRole.INDEPENDENT_TEACHER
    assert user.status == IndependentUserAccountStatus.ACTIVE


@pytest.mark.asyncio
async def test_post_independent_signup_rejects_duplicate_email() -> None:
    existing = IndependentUser(
        authentik_id="existing-id",
        email="dup@example.com",
        display_name="Existing",
        role=IndependentUserRole.INDEPENDENT_STUDENT,
        status=IndependentUserAccountStatus.ACTIVE,
    )
    _FakeIndependentUserRepo.store[existing.id] = existing
    _FakeIndependentUserRepo.by_email[existing.email] = existing

    async with _build_client() as client:
        resp = await client.post(
            "/api/v1/independent/signup",
            json={
                "email": "dup@example.com",
                "password": "securepass1",
                "display_name": "Another",
                "role": "independent_student",
                "language_preference": "ur",
            },
        )
    assert resp.status_code == 409
