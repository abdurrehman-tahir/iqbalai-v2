"""Content library namespace notification dispatcher — T-065."""

from __future__ import annotations

from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.notifications.publish import publish_notification
from app.infrastructure.notifications.templates.content_library import (
    DEFAULT_LOCALE,
    TEMPLATE_CHANNELS,
    render_content_library_template,
)

logger = structlog.get_logger(__name__)


async def notify_content_library_event(
    *,
    session: AsyncSession,
    template_key: str,
    recipient_user_id: str,
    school_id: str,
    locale: str = DEFAULT_LOCALE,
    variant: str = "default",
    metadata: dict[str, Any] | None = None,
    params: dict[str, str] | None = None,
) -> None:
    """Publish a content_library-namespace in-app notification."""
    active_channels = TEMPLATE_CHANNELS.get(template_key)
    if not active_channels:
        raise ValueError(f"No channel mapping for template '{template_key}'")

    rendered = render_content_library_template(
        template_key,
        locale=locale,
        variant=variant,
        params=params,
    )

    meta = {"template_key": template_key, "locale": locale, "variant": variant}
    if metadata:
        meta.update(metadata)

    if "in_app" in active_channels:
        await publish_notification(
            session=session,
            recipient_user_id=recipient_user_id,
            feature_namespace="content_library",
            template_key=template_key,
            title=rendered["title"],
            body=rendered["body"],
            school_id=school_id,
            metadata=meta,
        )

    logger.info(
        "content_library_notification_fired",
        template_key=template_key,
        recipient_user_id=recipient_user_id,
    )
