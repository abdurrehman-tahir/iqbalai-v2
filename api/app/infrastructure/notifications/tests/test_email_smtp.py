"""SMTP email sender tests."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.config import Settings
from app.infrastructure.notifications import email as email_module


@pytest.mark.asyncio
async def test_send_account_email_uses_smtp_when_configured() -> None:
    settings = Settings(
        EMAIL_PROVIDER="smtp",
        EMAIL_FROM="info@iqbalai.com",
        SMTP_HOST="mail.privateemail.com",
        SMTP_PORT=465,
        SMTP_USE_SSL=True,
        SMTP_USERNAME="info@iqbalai.com",
        SMTP_PASSWORD="secret",
    )

    with (
        patch.object(email_module, "get_settings", return_value=settings),
        patch.object(email_module, "_send_smtp_sync") as smtp_mock,
    ):
        await email_module.send_account_email(
            to="admin@example.com",
            subject="You're invited",
            body="Click here",
            template_key="account.invite_sent",
        )

    smtp_mock.assert_called_once()
    assert smtp_mock.call_args.kwargs["to"] == "admin@example.com"


def test_send_smtp_sync_uses_ssl_login() -> None:
    settings = Settings(
        EMAIL_FROM="info@iqbalai.com",
        SMTP_HOST="mail.privateemail.com",
        SMTP_PORT=465,
        SMTP_USE_SSL=True,
        SMTP_USERNAME="info@iqbalai.com",
        SMTP_PASSWORD="secret",
    )

    smtp_instance = MagicMock()
    smtp_cls = MagicMock(return_value=MagicMock(__enter__=lambda s: smtp_instance, __exit__=lambda *a: None))

    with patch.object(email_module.smtplib, "SMTP_SSL", smtp_cls):
        email_module._send_smtp_sync(
            settings=settings,
            to="admin@example.com",
            subject="Invite",
            body="Join now",
        )

    smtp_cls.assert_called_once_with("mail.privateemail.com", 465, timeout=30)
    smtp_instance.login.assert_called_once_with("info@iqbalai.com", "secret")
    smtp_instance.send_message.assert_called_once()
