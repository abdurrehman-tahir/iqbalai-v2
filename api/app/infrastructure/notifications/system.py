"""System namespace notification dispatcher (T-135, ARCH §9.21).

First real caller of the ``system`` namespace — mirrors ``notifications/lectures.py``,
plus a Platform-Admin fan-out helper since system alerts have no single known
recipient (unlike a teacher's own lecture events).
"""

from __future__ import annotations

from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.users.models import UserRole
from app.features.users.repository import UserRepository
from app.infrastructure.notifications.publish import publish_notification
from app.infrastructure.notifications.templates.system import (
    DEFAULT_LOCALE,
    TEMPLATE_CHANNELS,
    render_system_template,
)

logger = structlog.get_logger(__name__)


async def notify_system_event(
    *,
    session: AsyncSession,
    template_key: str,
    recipient_user_id: str,
    locale: str = DEFAULT_LOCALE,
    metadata: dict[str, Any] | None = None,
    params: dict[str, str] | None = None,
) -> None:
    """Publish a system-namespace in-app notification to one recipient."""
    active_channels = TEMPLATE_CHANNELS.get(template_key)
    if not active_channels:
        raise ValueError(f"No channel mapping for template '{template_key}'")

    rendered = render_system_template(template_key, locale=locale, params=params)

    meta = {"template_key": template_key, "locale": locale}
    if metadata:
        meta.update(metadata)

    if "in_app" in active_channels:
        await publish_notification(
            session=session,
            recipient_user_id=recipient_user_id,
            feature_namespace="system",
            template_key=template_key,
            title=rendered["title"],
            body=rendered["body"],
            school_id=None,
            metadata=meta,
        )

    logger.info(
        "system_notification_fired",
        template_key=template_key,
        recipient_user_id=recipient_user_id,
    )


async def notify_all_platform_admins(
    session: AsyncSession,
    *,
    template_key: str,
    metadata: dict[str, Any] | None = None,
    params: dict[str, str] | None = None,
) -> None:
    """Fan out one system notification to every active Platform Admin.

    Platform Admin has no locale preference tracked anywhere (no profile
    table — it's a system-level role, not a teaching one) so this always
    renders at ``DEFAULT_LOCALE``.
    """
    admins = await UserRepository(session).list_by_role(UserRole.PLATFORM_ADMIN)
    for admin in admins:
        await notify_system_event(
            session=session,
            template_key=template_key,
            recipient_user_id=admin.authentik_id,
            metadata=metadata,
            params=params,
        )
