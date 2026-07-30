"""Best-effort NATS publish for lecture generation lifecycle — T-116."""

from __future__ import annotations

from typing import Any

import structlog

from app.infrastructure.events.publisher import publish

logger = structlog.get_logger(__name__)

LECTURE_GENERATION_REQUESTED = "lecture.generation_requested"
LECTURE_VERSION_CREATED = "lecture.version.created"


async def publish_lecture_event(*, event_type: str, payload: dict[str, Any]) -> None:
    """Publish after commit; never raises into the caller path."""
    try:
        await publish(
            event_type,
            event_type,
            payload,
            tenant_id=str(payload.get("school_id", "")),
            tenant_type=str(payload.get("tenant_type", "school")),
            user_id=str(payload.get("teacher_user_id", "")),
        )
    except Exception as exc:
        logger.warning("lecture_event_publish_failed", event_type=event_type, error=str(exc))
