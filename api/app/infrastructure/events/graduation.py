"""Best-effort NATS publish for graduation lifecycle events — T-087."""

from __future__ import annotations

from typing import Any

import structlog

logger = structlog.get_logger(__name__)


async def publish_graduation_event(*, event_type: str, payload: dict[str, Any]) -> None:
    try:
        from app.infrastructure.events.publisher import publish

        await publish(event_type, event_type, payload)
    except Exception as exc:
        logger.warning(
            "graduation_event_publish_skipped",
            event_type=event_type,
            error=str(exc),
        )
