"""Account namespace notification dispatcher — T-038."""

from __future__ import annotations

from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.notifications.email import send_account_email
from app.infrastructure.notifications.publish import publish_notification
from app.infrastructure.notifications.templates.account import (
    DEFAULT_LOCALE,
    TEMPLATE_CHANNELS,
    render_account_template,
)

logger = structlog.get_logger(__name__)


async def notify_account_event(
    *,
    session: AsyncSession,
    template_key: str,
    locale: str = DEFAULT_LOCALE,
    variant: str = "default",
    recipient_user_id: str | None = None,
    recipient_email: str | None = None,
    school_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    params: dict[str, str] | None = None,
    channels: frozenset[str] | None = None,
) -> None:
    """Publish an account-namespace notification on configured channels."""
    active_channels = channels or TEMPLATE_CHANNELS.get(template_key)
    if not active_channels:
        raise ValueError(f"No channel mapping for template '{template_key}'")

    rendered = render_account_template(
        template_key,
        locale=locale,
        variant=variant,
        params=params,
    )

    meta = {"template_key": template_key, "locale": locale, "variant": variant}
    if metadata:
        meta.update(metadata)

    if "in_app" in active_channels:
        if not recipient_user_id:
            raise ValueError(f"in_app channel requires recipient_user_id for '{template_key}'")
        await publish_notification(
            session=session,
            recipient_user_id=recipient_user_id,
            feature_namespace="account",
            template_key=template_key,
            title=rendered["title"],
            body=rendered["body"],
            school_id=school_id,
            metadata=meta,
        )

    if "email" in active_channels:
        if not recipient_email:
            raise ValueError(f"email channel requires recipient_email for '{template_key}'")
        subject = rendered.get("subject", rendered["title"])
        await send_account_email(
            to=recipient_email,
            subject=subject,
            body=rendered["body"],
            template_key=template_key,
        )

    logger.info(
        "account_notification_fired",
        template_key=template_key,
        channels=sorted(active_channels),
        recipient_user_id=recipient_user_id,
        recipient_email=recipient_email,
    )
