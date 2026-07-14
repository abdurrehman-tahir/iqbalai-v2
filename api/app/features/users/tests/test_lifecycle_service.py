"""Unit tests for UserLifecycleService — T-033."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock

import pytest

from app.core.exceptions import NotFoundError, PreconditionFailedError, ValidationError
from app.features.users.lifecycle_service import UserLifecycleService
from app.features.users.models import User, UserAccountStatus, UserRole
from app.infrastructure.authentik.client import DevAuthentikClient


class _FakeUserRepo:
    users: dict[str, User] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def get_by_id(self, user_id: str) -> User | None:
        user = self.users.get(user_id)
        if user is None or user.deleted_at is not None:
            return None
        return user

    async def get_by_authentik_id(self, authentik_id: str) -> User | None:
        return next((u for u in self.users.values() if u.authentik_id == authentik_id), None)

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
            rows = [u for u in rows if u.school_id == school_id]
        elif district_id is not None:
            rows = [u for u in rows if u.district_id == district_id]
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
            if role == UserRole.PLATFORM_ADMIN:
                if user.district_id is None and user.school_id is None:
                    count += 1
            elif role == UserRole.DISTRICT_ADMIN and user.district_id == district_id:
                count += 1
            elif role == UserRole.SCHOOL_ADMIN and user.school_id == school_id:
                count += 1
        return count


def _user(
    *,
    id: str,
    role: UserRole,
    status: UserAccountStatus = UserAccountStatus.ACTIVE,
    district_id: str | None = None,
    school_id: str | None = None,
    authentik_id: str | None = None,
) -> User:
    now = datetime.now(timezone.utc)
    return User(
        id=id,
        authentik_id=authentik_id or f"ak-{id}",
        email=f"{id}@test.com",
        display_name=id,
        role=role,
        status=status,
        district_id=district_id,
        school_id=school_id,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture(autouse=True)
def _setup(monkeypatch: pytest.MonkeyPatch) -> None:
    _FakeUserRepo.users = {
        "sa-1": _user(
            id="sa-1",
            role=UserRole.SCHOOL_ADMIN,
            school_id="school-1",
            district_id="dist-1",
            authentik_id="ak-sa-1",
        ),
        "teacher-1": _user(
            id="teacher-1",
            role=UserRole.TEACHER,
            school_id="school-1",
            district_id="dist-1",
        ),
        "pa-1": _user(
            id="pa-1",
            role=UserRole.PLATFORM_ADMIN,
            authentik_id="ak-pa-1",
        ),
    }
    monkeypatch.setattr("app.features.users.lifecycle_service.UserRepository", _FakeUserRepo)
    monkeypatch.setattr("app.features.users.lifecycle_service.audit", AsyncMock())
    monkeypatch.setattr("app.features.users.lifecycle_service.notify_account_event", AsyncMock())


def _svc() -> UserLifecycleService:
    return UserLifecycleService(session=AsyncMock(), authentik=DevAuthentikClient())


async def test_suspend_teacher() -> None:
    svc = _svc()
    claims: dict[str, object] = {"sub": "ak-sa-1", "role": "school_admin", "school_id": "school-1"}
    updated = await svc.suspend_user("teacher-1", claims=claims, actor_id="ak-sa-1")
    assert updated.status == UserAccountStatus.SUSPENDED


async def test_reactivate_suspended_user() -> None:
    svc = _svc()
    _FakeUserRepo.users["teacher-1"].status = UserAccountStatus.SUSPENDED
    claims: dict[str, object] = {"sub": "ak-sa-1", "role": "school_admin", "school_id": "school-1"}
    updated = await svc.reactivate_user("teacher-1", claims=claims, actor_id="ak-sa-1")
    assert updated.status == UserAccountStatus.ACTIVE


async def test_cannot_reactivate_deactivated_user() -> None:
    svc = _svc()
    _FakeUserRepo.users["teacher-1"].status = UserAccountStatus.DEACTIVATED
    claims: dict[str, object] = {"sub": "ak-sa-1", "role": "school_admin", "school_id": "school-1"}
    with pytest.raises(ValidationError, match="Deactivated"):
        await svc.reactivate_user("teacher-1", claims=claims, actor_id="ak-sa-1")


async def test_last_platform_admin_cannot_self_deactivate() -> None:
    svc = _svc()
    claims: dict[str, object] = {"sub": "ak-pa-1", "role": "platform_admin"}
    with pytest.raises(PreconditionFailedError, match="self-deactivate"):
        await svc.deactivate_user("pa-1", claims=claims, actor_id="ak-pa-1")


async def test_cross_school_suspend_returns_404() -> None:
    svc = _svc()
    claims: dict[str, object] = {
        "sub": "ak-sa-2",
        "role": "school_admin",
        "school_id": "school-other",
    }
    with pytest.raises(NotFoundError):
        await svc.suspend_user("teacher-1", claims=claims, actor_id="ak-sa-2")
