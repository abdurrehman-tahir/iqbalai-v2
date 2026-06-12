"""API contract tests for invitation endpoints — T-030."""

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
from app.core.tests.test_idempotency import FakeRedis
from app.features.invites.models import UserInvite, UserInviteStatus
from app.features.schools.models import District, School
from app.infrastructure.authentik.client import DevAuthentikClient


class _FakeInviteRepo:
    store: dict[str, UserInvite] = {}
    by_token: dict[str, UserInvite] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def get_by_id(self, invite_id: str) -> UserInvite | None:
        return self.store.get(invite_id)

    async def get_by_token_hash(self, token_hash: str) -> UserInvite | None:
        return self.by_token.get(token_hash)

    async def get_pending_by_email(self, email: str) -> UserInvite | None:
        return next(
            (
                i
                for i in self.store.values()
                if i.email == email.lower() and i.status == UserInviteStatus.PENDING
            ),
            None,
        )

    async def create(self, invite: UserInvite) -> UserInvite:
        now = datetime.now(timezone.utc)
        invite.created_at = now
        invite.updated_at = now
        self.store[invite.id] = invite
        self.by_token[invite.token_hash] = invite
        return invite

    async def update(self, invite: UserInvite) -> UserInvite:
        self.store[invite.id] = invite
        self.by_token[invite.token_hash] = invite
        return invite

    async def expire_stale_pending(self, invite: UserInvite) -> UserInvite:
        return invite


class _FakeUserRepo:
    users: dict[str, object] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def get_by_email(self, email: str) -> object | None:
        return None

    async def create(self, user: object) -> object:
        return user


class _FakeDistrictRepo:
    def __init__(self, session: Any) -> None:
        pass

    async def get_by_id(self, id: str) -> District | None:
        return District(id=id, name="Test District", region="Punjab")


class _FakeSchoolRepo:
    def __init__(self, session: Any) -> None:
        pass

    async def get_by_id(self, id: str) -> School | None:
        if id == "school-1":
            return School(id="school-1", district_id="dist-1", name="Test School")
        return None


@pytest.fixture(autouse=True)
def _patch_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    _FakeInviteRepo.store = {}
    _FakeInviteRepo.by_token = {}
    monkeypatch.setattr("app.features.invites.service.UserInviteRepository", _FakeInviteRepo)
    monkeypatch.setattr("app.features.invites.service.UserRepository", _FakeUserRepo)
    monkeypatch.setattr("app.features.invites.service.DistrictRepository", _FakeDistrictRepo)
    monkeypatch.setattr("app.features.invites.service.SchoolRepository", _FakeSchoolRepo)
    monkeypatch.setattr("app.features.invites.service.send_invite_email", AsyncMock())
    monkeypatch.setattr("app.features.invites.service.audit", AsyncMock())
    monkeypatch.setattr(
        "app.features.invites.service.get_authentik_client", lambda: DevAuthentikClient()
    )
    monkeypatch.setattr("app.features.invites.service.get_redis", lambda: FakeRedis())


def _build_client(role: str = "platform_admin", district_id: str | None = None) -> AsyncClient:
    app = FastAPI()
    app.include_router(v1_router, prefix="/api/v1")
    setup_exception_handlers(app)

    async def _fake_db() -> AsyncGenerator[Any, None]:
        yield AsyncMock()

    def _claims() -> dict[str, object]:
        data: dict[str, object] = {"sub": "admin-1", "role": role, "tenant_id": "t1"}
        if district_id is not None:
            data["district_id"] = district_id
        return data

    app.dependency_overrides[get_db] = _fake_db
    app.dependency_overrides[get_current_user] = _claims
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


async def test_invite_district_admin_returns_201() -> None:
    async with _build_client() as client:
        resp = await client.post(
            "/api/v1/admin/users",
            json={
                "email": "da@test.com",
                "display_name": "District Admin",
                "role": "district_admin",
                "district_id": "dist-1",
            },
        )
    assert resp.status_code == 201
    body = resp.json()
    assert body["data"]["email"] == "da@test.com"
    assert body["data"]["invited_role"] == "district_admin"
    assert body["data"]["status"] == "pending"


async def test_non_admin_invite_forbidden() -> None:
    async with _build_client(role="teacher") as client:
        resp = await client.post(
            "/api/v1/admin/users",
            json={
                "email": "da@test.com",
                "display_name": "District Admin",
                "role": "district_admin",
                "district_id": "dist-1",
            },
        )
    assert resp.status_code == 403


async def test_district_admin_invites_school_admin_returns_201() -> None:
    async with _build_client(role="district_admin", district_id="dist-1") as client:
        resp = await client.post(
            "/api/v1/admin/users",
            json={
                "email": "sa@test.com",
                "display_name": "School Admin",
                "role": "school_admin",
                "school_id": "school-1",
            },
        )
    assert resp.status_code == 201
    body = resp.json()
    assert body["data"]["invited_role"] == "school_admin"
    assert body["data"]["school_id"] == "school-1"


async def test_accept_invite_public_no_auth() -> None:
    async with _build_client() as client:
        created = await client.post(
            "/api/v1/admin/users",
            json={
                "email": "accept@test.com",
                "display_name": "Accept",
                "role": "district_admin",
                "district_id": "dist-1",
            },
        )
        invite_id = created.json()["data"]["id"]
        # Extract raw token from fake repo (tests only)
        from app.features.invites.service import _new_token_pair

        raw, token_hash = _new_token_pair()
        invite = _FakeInviteRepo.store[invite_id]
        invite.token_hash = token_hash
        _FakeInviteRepo.by_token[token_hash] = invite

        resp = await client.post(
            "/api/v1/auth/accept-invite",
            json={"token": raw, "action": "accept", "password": "securepass1"},
        )
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "accepted"
