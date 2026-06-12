"""Unit tests for InviteService — T-030."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock

import pytest

from app.core.exceptions import ConflictError, PreconditionFailedError, ValidationError
from app.core.tests.test_idempotency import FakeRedis
from app.features.invites.models import UserInvite, UserInviteStatus
from app.features.invites.schemas import AcceptInviteRequest, AdminUserInviteCreate
from app.features.invites.service import InviteService, _hash_token, _new_token_pair
from app.features.schools.models import District
from app.features.users.models import User, UserRole
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
        invite.resent_count = invite.resent_count or 0
        invite.rejected_count = invite.rejected_count or 0
        self.store[invite.id] = invite
        self.by_token[invite.token_hash] = invite
        return invite

    async def update(self, invite: UserInvite) -> UserInvite:
        self.store[invite.id] = invite
        self.by_token[invite.token_hash] = invite
        return invite

    async def expire_stale_pending(self, invite: UserInvite) -> UserInvite:
        if invite.status == UserInviteStatus.PENDING and invite.expires_at < datetime.now(
            timezone.utc
        ):
            invite.status = UserInviteStatus.EXPIRED
            await self.update(invite)
        return invite


class _FakeUserRepo:
    users: dict[str, User] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def get_by_email(self, email: str) -> User | None:
        return next((u for u in self.users.values() if u.email == email.lower()), None)

    async def create(self, user: User) -> User:
        self.users[user.id] = user
        return user


class _FakeDistrictRepo:
    districts: dict[str, District] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def get_by_id(self, id: str) -> District | None:
        return self.districts.get(id)


@pytest.fixture(autouse=True)
def _setup(monkeypatch: pytest.MonkeyPatch) -> None:
    _FakeInviteRepo.store = {}
    _FakeInviteRepo.by_token = {}
    _FakeUserRepo.users = {}
    _FakeDistrictRepo.districts = {
        "dist-1": District(id="dist-1", name="Punjab District 1", region="Punjab")
    }
    monkeypatch.setattr("app.features.invites.service.UserInviteRepository", _FakeInviteRepo)
    monkeypatch.setattr("app.features.invites.service.UserRepository", _FakeUserRepo)
    monkeypatch.setattr("app.features.invites.service.DistrictRepository", _FakeDistrictRepo)
    monkeypatch.setattr("app.features.invites.service.send_invite_email", AsyncMock())
    monkeypatch.setattr("app.features.invites.service.audit", AsyncMock())
    monkeypatch.setattr("app.features.invites.service.get_redis", lambda: FakeRedis())


def _svc() -> InviteService:
    return InviteService(session=AsyncMock(), authentik=DevAuthentikClient())


async def test_create_invite_success() -> None:
    svc = _svc()
    payload = AdminUserInviteCreate(
        email="admin@district.test",
        display_name="District Admin",
        role=UserRole.DISTRICT_ADMIN,
        district_id="dist-1",
    )
    invite, raw = await svc.create_invite(
        payload, actor_id="platform-1", caller_role="platform_admin"
    )
    assert invite.status == UserInviteStatus.PENDING
    assert invite.email == "admin@district.test"
    assert invite.invited_role == UserRole.DISTRICT_ADMIN
    assert len(raw) > 20


async def test_duplicate_email_raises_conflict() -> None:
    svc = _svc()
    _FakeUserRepo.users["u1"] = User(
        authentik_id="ak-1",
        email="taken@test.com",
        display_name="Taken",
        role=UserRole.DISTRICT_ADMIN,
    )
    payload = AdminUserInviteCreate(
        email="taken@test.com",
        display_name="New",
        role=UserRole.DISTRICT_ADMIN,
        district_id="dist-1",
    )
    with pytest.raises(ConflictError):
        await svc.create_invite(payload, actor_id="platform-1", caller_role="platform_admin")


async def test_accept_invite_creates_user() -> None:
    svc = _svc()
    payload = AdminUserInviteCreate(
        email="accept@test.com",
        display_name="Accept Me",
        role=UserRole.DISTRICT_ADMIN,
        district_id="dist-1",
    )
    invite, raw = await svc.create_invite(
        payload, actor_id="platform-1", caller_role="platform_admin"
    )
    result = await svc.accept_invite(
        AcceptInviteRequest(token=raw, action="accept", password="securepass1")
    )
    assert result["status"] == "accepted"
    assert len(_FakeUserRepo.users) == 1
    user = next(iter(_FakeUserRepo.users.values()))
    assert user.role == UserRole.DISTRICT_ADMIN
    assert user.district_id == "dist-1"
    assert _FakeInviteRepo.store[invite.id].status == UserInviteStatus.ACCEPTED


async def test_expired_token_rejected() -> None:
    svc = _svc()
    raw, token_hash = _new_token_pair()
    invite = UserInvite(
        email="expired@test.com",
        display_name="Expired",
        invited_by_user_id="platform-1",
        invited_role=UserRole.DISTRICT_ADMIN,
        district_id="dist-1",
        token_hash=token_hash,
        authentik_id="ak-exp",
        expires_at=datetime.now(timezone.utc) - timedelta(days=1),
        status=UserInviteStatus.PENDING,
    )
    await _FakeInviteRepo(None).create(invite)
    with pytest.raises(ValidationError, match="expired"):
        await svc.accept_invite(
            AcceptInviteRequest(token=raw, action="accept", password="pass12345")
        )


async def test_three_rejections_lock_invite() -> None:
    svc = _svc()
    payload = AdminUserInviteCreate(
        email="reject@test.com",
        display_name="Reject Me",
        role=UserRole.DISTRICT_ADMIN,
        district_id="dist-1",
    )
    invite, raw = await svc.create_invite(
        payload, actor_id="platform-1", caller_role="platform_admin"
    )

    for _ in range(3):
        # Re-open pending after each reject except the last locks it
        inv = _FakeInviteRepo.store[invite.id]
        if inv.status == UserInviteStatus.REJECTED:
            inv.status = UserInviteStatus.PENDING
            await _FakeInviteRepo(None).update(inv)
        await svc.accept_invite(AcceptInviteRequest(token=raw, action="reject"))

    locked = _FakeInviteRepo.store[invite.id]
    assert locked.status == UserInviteStatus.LOCKED
    assert locked.rejected_count == 3

    with pytest.raises(PreconditionFailedError):
        await svc.accept_invite(
            AcceptInviteRequest(token=raw, action="accept", password="pass12345")
        )


async def test_resend_issues_new_token() -> None:
    svc = _svc()
    payload = AdminUserInviteCreate(
        email="resend@test.com",
        display_name="Resend Me",
        role=UserRole.DISTRICT_ADMIN,
        district_id="dist-1",
    )
    invite, _old = await svc.create_invite(
        payload, actor_id="platform-1", caller_role="platform_admin"
    )
    old_hash = invite.token_hash

    updated, new_raw = await svc.resend_invite(invite.id, actor_id="platform-1")
    assert updated.resent_count == 1
    assert updated.token_hash != old_hash
    assert _hash_token(new_raw) == updated.token_hash
