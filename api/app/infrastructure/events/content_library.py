"""Best-effort NATS publish for school content library mutations — T-065."""

from __future__ import annotations

from typing import Any

import structlog

logger = structlog.get_logger(__name__)


async def publish_content_library_mutation(
    event_suffix: str,
    payload: dict[str, Any],
    *,
    school_id: str,
    user_id: str,
) -> None:
    """Publish a content library mutation event on the users stream (best-effort)."""
    try:
        from app.infrastructure.events.publisher import publish

        await publish(
            subject=f"users.content_library.{event_suffix}",
            event_type=f"content_library.{event_suffix}",
            payload=payload,
            tenant_id=school_id,
            user_id=user_id,
        )
    except Exception as exc:
        logger.warning(
            "content_library_event_publish_skipped",
            event_suffix=event_suffix,
            error=str(exc),
        )
