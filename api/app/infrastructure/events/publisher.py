"""NATS JetStream event publisher.

Per ARCH §9: all events use the standard envelope with tenant_id, tenant_type,
user_id, session_id, occurred_at, event_type, payload.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import nats
import structlog

from app.config import get_settings

logger = structlog.get_logger(__name__)


def _build_envelope(
    event_type: str,
    payload: dict[str, Any],
    tenant_id: str,
    tenant_type: str,
    user_id: str,
    session_id: str = "",
) -> dict[str, Any]:
    """Build a standard event envelope per ARCH §9."""
    return {
        "tenant_id": tenant_id,
        "tenant_type": tenant_type,
        "user_id": user_id,
        "session_id": session_id,
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,
        "payload": payload,
    }


async def publish(
    subject: str,
    event_type: str,
    payload: dict[str, Any],
    tenant_id: str = "",
    tenant_type: str = "school",
    user_id: str = "",
    session_id: str = "",
) -> None:
    """Publish a JetStream event to the given subject.

    Per ARCH §9.9: publish AFTER the DB transaction commits.
    """
    settings = get_settings()
    envelope = _build_envelope(
        event_type=event_type,
        payload=payload,
        tenant_id=tenant_id,
        tenant_type=tenant_type,
        user_id=user_id,
        session_id=session_id,
    )
    message = json.dumps(envelope).encode()

    nc = await nats.connect(settings.NATS_URL)
    js = nc.jetstream()
    try:
        await js.publish(subject, message)
        logger.info(
            "event_published",
            subject=subject,
            event_type=event_type,
            tenant_id=tenant_id,
        )
    except Exception as exc:
        logger.error("event_publish_failed", subject=subject, error=str(exc))
        raise
    finally:
        await nc.close()
