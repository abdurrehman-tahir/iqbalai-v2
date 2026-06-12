"""Account notification dispatcher tests — T-038."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.infrastructure.notifications.account import notify_account_event


@pytest.mark.asyncio
async def test_notify_account_event_in_app_and_email() -> None:
    session = AsyncMock()
    with (
        patch(
            "app.infrastructure.notifications.account.publish_notification",
            AsyncMock(),
        ) as mock_publish,
        patch(
            "app.infrastructure.notifications.account.send_account_email",
            AsyncMock(),
        ) as mock_email,
    ):
        await notify_account_event(
            session=session,
            template_key="account.reactivated",
            recipient_user_id="user-1",
            recipient_email="user@test.com",
            variant="target",
        )

    mock_publish.assert_awaited_once()
    mock_email.assert_awaited_once()


@pytest.mark.asyncio
async def test_notify_invite_sent_email_only() -> None:
    session = AsyncMock()
    with (
        patch(
            "app.infrastructure.notifications.account.publish_notification",
            AsyncMock(),
        ) as mock_publish,
        patch(
            "app.infrastructure.notifications.account.send_account_email",
            AsyncMock(),
        ) as mock_email,
    ):
        await notify_account_event(
            session=session,
            template_key="account.invite_sent",
            recipient_email="new@test.com",
            params={"inviter_name": "Admin", "invite_url": "https://x/y"},
        )

    mock_publish.assert_not_awaited()
    mock_email.assert_awaited_once()
