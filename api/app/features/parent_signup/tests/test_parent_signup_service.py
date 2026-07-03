"""Unit tests for parent auto-suspend and resume — T-080."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest

from app.features.parent_signup.models import ParentProfile
from app.features.parent_signup.service import (
    PARENT_STATE_ACTIVE_UNLINKED,
    ParentSignupService,
)
from app.features.users.models import User, UserAccountStatus, UserRole


class _FakeUserRepo:
    def __init__(self) -> None:
        self.users: dict[str, User] = {}

    async def update(self, user: User) -> User:
        self.users[user.id] = user
        return user


class _FakeProfileRepo:
    def __init__(self) -> None:
        self.profiles: dict[str, ParentProfile] = {}

    async def get_by_user_id(self, user_id: str) -> ParentProfile | None:
        return self.profiles.get(user_id)

    async def update(self, profile: ParentProfile) -> ParentProfile:
        self.profiles[profile.user_id] = profile
        return profile

    async def list_stale_unlinked(self, cutoff: datetime) -> list[tuple[User, ParentProfile]]:
        stale: list[tuple[User, ParentProfile]] = []
        for user in _FakeUserRepo().users.values():
            profile = self.profiles.get(user.id)
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


def _parent_user(*, status: UserAccountStatus = UserAccountStatus.ACTIVE) -> User:
    return User(
        id="parent-1",
        authentik_id="auth-1",
        email="parent@example.com",
        display_name="Parent",
        role=UserRole.PARENT,
        status=status,
    )


def _profile(*, verified: bool = True, unlinked_since: datetime | None = None) -> ParentProfile:
    return ParentProfile(
        user_id="parent-1",
        name="Parent",
        language_preference="en",
        is_email_verified=verified,
        unlinked_since=unlinked_since,
    )


@pytest.mark.asyncio
async def test_activate_on_login_sets_parent_active_unlinked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = _parent_user()
    profile = _profile(verified=False, unlinked_since=None)
    profile_repo = _FakeProfileRepo()
    profile_repo.profiles["parent-1"] = profile

    svc = ParentSignupService(session=AsyncMock())  # type: ignore[arg-type]
    svc._profiles = profile_repo  # type: ignore[assignment]

    result = await svc.activate_on_login(user)
    assert result is not None
    assert result.is_email_verified is True
    assert result.unlinked_since is not None
    assert ParentSignupService.parent_state_for_profile(result) == PARENT_STATE_ACTIVE_UNLINKED


@pytest.mark.asyncio
async def test_try_resume_unlinked_parent_reactivates_suspended_parent() -> None:
    user = _parent_user(status=UserAccountStatus.SUSPENDED)
    old_unlinked = datetime.now(timezone.utc) - timedelta(days=100)
    profile = _profile(unlinked_since=old_unlinked)

    user_repo = _FakeUserRepo()
    user_repo.users[user.id] = user
    profile_repo = _FakeProfileRepo()
    profile_repo.profiles[user.id] = profile

    svc = ParentSignupService(session=AsyncMock())  # type: ignore[arg-type]
    svc._users = user_repo  # type: ignore[assignment]
    svc._profiles = profile_repo  # type: ignore[assignment]

    resumed = await svc.try_resume_unlinked_parent(user)
    assert resumed is not None
    assert resumed.status == UserAccountStatus.ACTIVE
    assert profile_repo.profiles[user.id].unlinked_since is not None
    assert profile_repo.profiles[user.id].unlinked_since > old_unlinked


@pytest.mark.asyncio
async def test_suspend_stale_unlinked_parents(monkeypatch: pytest.MonkeyPatch) -> None:
    user = _parent_user()
    profile = _profile(
        unlinked_since=datetime.now(timezone.utc) - timedelta(days=91),
    )

    user_repo = _FakeUserRepo()
    user_repo.users[user.id] = user

    async def _list_stale(cutoff: datetime) -> list[tuple[User, ParentProfile]]:
        return [(user, profile)]

    profile_repo = _FakeProfileRepo()
    profile_repo.list_stale_unlinked = _list_stale  # type: ignore[method-assign]

    svc = ParentSignupService(session=AsyncMock())  # type: ignore[arg-type]
    svc._users = user_repo  # type: ignore[assignment]
    svc._profiles = profile_repo  # type: ignore[assignment]
    monkeypatch.setattr("app.features.parent_signup.service.send_account_email", AsyncMock())

    count = await svc.suspend_stale_unlinked_parents()
    assert count == 1
    assert user_repo.users[user.id].status == UserAccountStatus.SUSPENDED
