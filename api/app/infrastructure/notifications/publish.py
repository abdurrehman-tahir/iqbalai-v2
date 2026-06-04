"""Notification publisher — writes to DB + emits Redis pub/sub for live push (T-023).

Per ARCH §9.12 (Redis pub/sub) and §9.21 (7 locked namespaces).
"""

from __future__ import annotations

import json
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)

# 7 locked namespaces per ARCH §9.21
VALID_NAMESPACES = frozenset(
    {
        "lectures",
        "self_study",
        "quiz",
        "connections",
        "content_library",
        "system",
        "account",
    }
)


async def publish_notification(
    *,
    session: AsyncSession,
    recipient_user_id: str,
    feature_namespace: str,
    template_key: str,
    title: str,
    body: str,
    school_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Write a notification row to DB.

    Redis pub/sub for real-time push added in M-09 when WebSocket infra is wired.
    FCM push stub deferred to Phase 2 per T-023 scope.
    """
    # Deferred import avoids circular dependency between infrastructure and features layers
    from app.features.notifications.models import Notification

    if feature_namespace not in VALID_NAMESPACES:
        raise ValueError(
            f"Unknown namespace '{feature_namespace}'. Must be one of {VALID_NAMESPACES}"
        )

    notif = Notification(
        recipient_user_id=recipient_user_id,
        feature_namespace=feature_namespace,
        template_key=template_key,
        title=title,
        body=body,
        school_id=school_id,
        metadata_json=json.dumps(metadata) if metadata else None,
    )
    session.add(notif)
    await session.commit()

    logger.info(
        "notification_published",
        recipient=recipient_user_id,
        namespace=feature_namespace,
        template_key=template_key,
    )
