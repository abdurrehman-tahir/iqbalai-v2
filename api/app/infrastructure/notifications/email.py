"""Email sender — invite and notification delivery (STACK_LOCK §6)."""

from __future__ import annotations

import structlog

from app.config import get_settings

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

    logger.warning(
        "account_email_provider_not_implemented",
        provider=settings.EMAIL_PROVIDER,
        to=to,
        template_key=template_key,
    )
