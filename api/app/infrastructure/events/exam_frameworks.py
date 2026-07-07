"""Best-effort NATS publish for exam-framework lifecycle events (T-097, ARCH §9).

Mirrors the graduation event wrapper: publish-after-commit, best-effort — a NATS outage
must not fail the framework lifecycle transition that already committed.
"""

from __future__ import annotations

from typing import Any

import structlog

logger = structlog.get_logger(__name__)


async def publish_framework_event(*, event_type: str, payload: dict[str, Any]) -> None:
    try:
        from app.infrastructure.events.publisher import publish

        await publish(event_type, event_type, payload)
    except Exception as exc:
        logger.warning(
            "framework_event_publish_skipped",
            event_type=event_type,
            error=str(exc),
        )
