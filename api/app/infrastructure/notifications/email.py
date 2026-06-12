"""Email sender — invite and notification delivery (STACK_LOCK §6)."""

from __future__ import annotations

import asyncio
import smtplib
from email.message import EmailMessage

import structlog

from app.config import Settings, get_settings

logger = structlog.get_logger(__name__)


async def send_invite_email(
    *,
    to: str,
    invite_url: str,
    inviter_name: str,
    locale: str = "en",
) -> None:
    """Send an admin invitation email using the account.invite_sent template."""
    from app.infrastructure.notifications.templates.account import render_account_template

    rendered = render_account_template(
        "account.invite_sent",
        locale=locale,
        params={"inviter_name": inviter_name, "invite_url": invite_url},
    )
    await send_account_email(
        to=to,
        subject=rendered["subject"],
        body=rendered["body"],
        template_key="account.invite_sent",
    )


def _send_smtp_sync(
    *,
    settings: Settings,
    to: str,
    subject: str,
    body: str,
) -> None:
    if not settings.SMTP_HOST or not settings.SMTP_USERNAME or not settings.SMTP_PASSWORD:
        raise RuntimeError("SMTP is not configured — set SMTP_HOST, SMTP_USERNAME, SMTP_PASSWORD")

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.EMAIL_FROM
    msg["To"] = to
    msg.set_content(body)

    if settings.SMTP_USE_SSL:
        with smtplib.SMTP_SSL(
            settings.SMTP_HOST,
            settings.SMTP_PORT,
            timeout=settings.SMTP_TIMEOUT,
        ) as smtp:
            smtp.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            smtp.send_message(msg)
        return

    with smtplib.SMTP(
        settings.SMTP_HOST,
        settings.SMTP_PORT,
        timeout=settings.SMTP_TIMEOUT,
    ) as smtp:
        if settings.SMTP_USE_TLS:
            smtp.starttls()
        smtp.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
        smtp.send_message(msg)


async def send_account_email(*, to: str, subject: str, body: str, template_key: str) -> None:
    """Send a templated account notification email."""
    settings = get_settings()

    if settings.EMAIL_PROVIDER == "log":
        logger.info(
            "account_email_sent",
            to=to,
            subject=subject,
            template_key=template_key,
            body_preview=body[:200],
        )
        return

    if settings.EMAIL_PROVIDER == "smtp":
        await asyncio.to_thread(
            _send_smtp_sync,
            settings=settings,
            to=to,
            subject=subject,
            body=body,
        )
        logger.info(
            "account_email_sent",
            to=to,
            subject=subject,
            template_key=template_key,
            provider="smtp",
        )
        return

    logger.warning(
        "account_email_provider_not_implemented",
        provider=settings.EMAIL_PROVIDER,
        to=to,
        template_key=template_key,
    )
