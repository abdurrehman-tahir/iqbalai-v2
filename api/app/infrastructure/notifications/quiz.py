"""Quiz namespace notification dispatcher (T-149)."""

from __future__ import annotations

from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.notifications.publish import publish_notification
from app.infrastructure.notifications.templates.quiz import (
    DEFAULT_LOCALE,
    TEMPLATE_CHANNELS,
    render_quiz_template,
)

logger = structlog.get_logger(__name__)


async def notify_quiz_event(
    *,
    session: AsyncSession,
    template_key: str,
    recipient_user_id: str,
    school_id: str | None = None,
    locale: str = DEFAULT_LOCALE,
    metadata: dict[str, Any] | None = None,
    params: dict[str, str] | None = None,
) -> None:
    active_channels = TEMPLATE_CHANNELS.get(template_key)
    if not active_channels:
        raise ValueError(f"No channel mapping for template '{template_key}'")

    rendered = render_quiz_template(template_key, locale=locale, params=params)

    meta = {"template_key": template_key, "locale": locale}
    if metadata:
        meta.update(metadata)

    if "in_app" in active_channels:
        await publish_notification(
            session=session,
            recipient_user_id=recipient_user_id,
            feature_namespace="quiz",
            template_key=template_key,
            title=rendered["title"],
            body=rendered["body"],
            school_id=school_id,
            metadata=meta,
        )

    logger.info(
        "quiz_notification_fired",
        template_key=template_key,
        recipient_user_id=recipient_user_id,
    )
