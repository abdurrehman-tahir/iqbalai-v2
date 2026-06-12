"""API contract tests for admin user lifecycle — T-033."""

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
from app.features.users.models import User, UserAccountStatus, UserRole


class _FakeUserRepo:
    users: dict[str, User] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def get_by_id(self, user_id: str) -> User | None:
        user = self.users.get(user_id)
        if user is None or user.deleted_at is not None:
            return None
        return user

    async def update(self, user: User) -> User:
        self.users[user.id] = user
        return user

    async def list_scoped(
        self,
        *,
        district_id: str | None = None,
        school_id: str | None = None,
    ) -> list[User]:
        rows = [u for u in self.users.values() if u.deleted_at is None]
        if school_id is not None:
            return [u for u in rows if u.school_id == school_id]
        if district_id is not None:
            return [u for u in rows if u.district_id == district_id]
        return rows

    async def count_active_admins(
        self,
        *,
        role: UserRole,
        district_id: str | None = None,
        school_id: str | None = None,
    ) -> int:
        count = 0
        for user in self.users.values():
            if user.deleted_at is not None:
                continue
            if user.status != UserAccountStatus.ACTIVE or user.role != role:
                continue
            if role == UserRole.SCHOOL_ADMIN and user.school_id == school_id:
                count += 1
        return count


@pytest.fixture(autouse=True)
def _patch(monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime.now(timezone.utc)
    _FakeUserRepo.users = {
        "u1": User(
            id="u1",
            authentik_id="ak-u1",
            email="teacher@test.com",
            display_name="Teacher",
            role=UserRole.TEACHER,
            status=UserAccountStatus.ACTIVE,
            school_id="school-1",
            district_id="dist-1",
            created_at=now,
            updated_at=now,
        ),
    }
    monkeypatch.setattr("app.features.users.lifecycle_service.UserRepository", _FakeUserRepo)
    monkeypatch.setattr("app.features.users.lifecycle_service.audit", AsyncMock())
    monkeypatch.setattr(
        "app.features.users.lifecycle_service.get_authentik_client",
        lambda: AsyncMock(deactivate_user=AsyncMock(), activate_user=AsyncMock()),
    )


def _build_client(role: str = "school_admin", school_id: str = "school-1") -> AsyncClient:
    app = FastAPI()
    app.include_router(v1_router, prefix="/api/v1")
    setup_exception_handlers(app)

    async def _fake_db() -> AsyncGenerator[Any, None]:
        yield AsyncMock()

    def _claims() -> dict[str, object]:
        return {"sub": "ak-admin", "role": role, "school_id": school_id, "district_id": "dist-1"}

    app.dependency_overrides[get_db] = _fake_db
    app.dependency_overrides[get_current_user] = _claims
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def test_list_users_returns_200() -> None:
    async with _build_client() as client:
        resp = await client.get("/api/v1/admin/users/")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["data"]) == 1
    assert body["data"][0]["email"] == "teacher@test.com"


async def test_suspend_user_returns_200() -> None:
    async with _build_client() as client:
        resp = await client.post("/api/v1/admin/users/u1/suspend")
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "suspended"


async def test_cross_school_suspend_returns_404() -> None:
    async with _build_client(school_id="school-other") as client:
        resp = await client.post("/api/v1/admin/users/u1/suspend")
    assert resp.status_code == 404
