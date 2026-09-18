"""System notification dispatcher tests — T-135 (Platform-Admin fan-out)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.features.users.models import User, UserAccountStatus, UserRole
from app.infrastructure.notifications.system import (
    notify_all_platform_admins,
    notify_system_event,
)

ADMIN_1 = User(
    id="admin-1",
    authentik_id="auth-admin-1",
    email="admin1@example.com",
    display_name="Admin One",
    role=UserRole.PLATFORM_ADMIN,
    status=UserAccountStatus.ACTIVE,
    school_id=None,
)
ADMIN_2 = User(
    id="admin-2",
    authentik_id="auth-admin-2",
    email="admin2@example.com",
    display_name="Admin Two",
    role=UserRole.PLATFORM_ADMIN,
    status=UserAccountStatus.ACTIVE,
    school_id=None,
)


@pytest.mark.asyncio
async def test_notify_system_event_publishes_in_app() -> None:
    session = AsyncMock()
    with patch(
        "app.infrastructure.notifications.system.publish_notification", AsyncMock()
    ) as mock_publish:
        await notify_system_event(
            session=session,
            template_key="system.plagiarism_flagged",
            recipient_user_id="auth-admin-1",
            params={"similarity_pct": "90"},
        )

    mock_publish.assert_awaited_once()
    call_kwargs = mock_publish.call_args.kwargs
    assert call_kwargs["feature_namespace"] == "system"
    assert call_kwargs["recipient_user_id"] == "auth-admin-1"
    assert call_kwargs["school_id"] is None


@pytest.mark.asyncio
async def test_notify_system_event_raises_for_unmapped_template() -> None:
    session = AsyncMock()
    with pytest.raises(ValueError, match="No channel mapping"):
        await notify_system_event(
            session=session,
            template_key="system.not_a_real_key",
            recipient_user_id="auth-admin-1",
        )


@pytest.mark.asyncio
async def test_notify_all_platform_admins_fans_out_to_every_admin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = AsyncMock()

    class _FakeUserRepository:
        def __init__(self, _session: object) -> None:
            pass

        async def list_by_role(self, role: UserRole) -> list[User]:
            assert role == UserRole.PLATFORM_ADMIN
            return [ADMIN_1, ADMIN_2]

    monkeypatch.setattr(
        "app.infrastructure.notifications.system.UserRepository", _FakeUserRepository
    )
    notify_mock = AsyncMock()
    monkeypatch.setattr("app.infrastructure.notifications.system.notify_system_event", notify_mock)

    await notify_all_platform_admins(
        session,
        template_key="system.plagiarism_flagged",
        params={"similarity_pct": "93"},
    )

    assert notify_mock.await_count == 2
    recipient_ids = {call.kwargs["recipient_user_id"] for call in notify_mock.await_args_list}
    assert recipient_ids == {"auth-admin-1", "auth-admin-2"}


@pytest.mark.asyncio
async def test_notify_all_platform_admins_noop_when_none_exist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = AsyncMock()

    class _FakeUserRepository:
        def __init__(self, _session: object) -> None:
            pass

        async def list_by_role(self, role: UserRole) -> list[User]:
            return []

    monkeypatch.setattr(
        "app.infrastructure.notifications.system.UserRepository", _FakeUserRepository
    )
    notify_mock = AsyncMock()
    monkeypatch.setattr("app.infrastructure.notifications.system.notify_system_event", notify_mock)

    await notify_all_platform_admins(session, template_key="system.plagiarism_flagged")

    notify_mock.assert_not_awaited()
