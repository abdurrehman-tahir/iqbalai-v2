"""Email sender — invite and notification delivery (STACK_LOCK §6)."""

from __future__ import annotations

import structlog

from app.config import get_settings

logger = structlog.get_logger(__name__)


async def send_invite_email(*, to: str, invite_url: str, inviter_name: str) -> None:
    """Send an admin invitation email with the accept-invite link.

    In dev (EMAIL_PROVIDER=log) the message is written to structured logs so
    MailHog is optional; production uses Brevo/Resend when configured.
    """
    settings = get_settings()
    subject = "You have been invited to IqbalAI"
    body = (
        f"Hello,\n\n"
        f"{inviter_name} has invited you to join IqbalAI as an administrator.\n\n"
        f"Accept your invitation (valid for 7 days):\n{invite_url}\n\n"
        f"If you did not expect this email, you can ignore it."
    )

    if settings.EMAIL_PROVIDER == "log":
        logger.info(
            "invite_email_sent",
            to=to,
            subject=subject,
            invite_url=invite_url,
            body_preview=body[:200],
        )
        return

    # Production providers wired in a follow-up; log-only keeps T-030 self-contained.
    logger.warning(
        "invite_email_provider_not_implemented",
        provider=settings.EMAIL_PROVIDER,
        to=to,
        invite_url=invite_url,
    )
