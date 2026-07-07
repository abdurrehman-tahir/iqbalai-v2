"""Exam-framework notification dispatcher (T-097).

Framework events reuse locked §9.21 namespaces: the template-key prefix is the namespace
(``system.framework_*`` for Platform-Admin alerts, ``self_study.framework_version_available``
for students). This keeps the notification out of a new (unregistered) ``framework``
namespace while still surfacing every framework lifecycle event.
"""

from __future__ import annotations

from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.notifications.publish import publish_notification
from app.infrastructure.notifications.templates.framework import (
    DEFAULT_LOCALE,
    TEMPLATE_CHANNELS,
    render_framework_template,
)

logger = structlog.get_logger(__name__)


async def notify_framework_event(
    *,
    session: AsyncSession,
    template_key: str,
    recipient_user_id: str,
    locale: str = DEFAULT_LOCALE,
    school_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    params: dict[str, str] | None = None,
) -> None:
    """Publish an in-app framework notification under the key's namespace prefix."""
    active_channels = TEMPLATE_CHANNELS.get(template_key)
    if not active_channels:
        raise ValueError(f"No channel mapping for template '{template_key}'")

    # The namespace is the template-key prefix (e.g. "system" or "self_study").
    namespace = template_key.split(".", 1)[0]
    rendered = render_framework_template(
        template_key, locale=locale, variant="default", params=params
    )

    meta = {"template_key": template_key, "locale": locale}
    if metadata:
        meta.update(metadata)

    if "in_app" in active_channels:
        await publish_notification(
            session=session,
            recipient_user_id=recipient_user_id,
            feature_namespace=namespace,
            template_key=template_key,
            title=rendered["title"],
            body=rendered["body"],
            school_id=school_id,
            metadata=meta,
        )

    logger.info(
        "framework_notification_fired",
        template_key=template_key,
        recipient_user_id=recipient_user_id,
    )
