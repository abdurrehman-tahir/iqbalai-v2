"""Best-effort NATS publish for M-03 structure mutations."""

from __future__ import annotations

from typing import Any

import structlog

logger = structlog.get_logger(__name__)


async def publish_structure_mutation(
    event_suffix: str,
    payload: dict[str, Any],
    *,
    school_id: str,
    user_id: str,
) -> None:
    """Publish a structure mutation event on the users stream (best-effort)."""
    try:
        from app.infrastructure.events.publisher import publish

        await publish(
            subject=f"users.structure.{event_suffix}",
            event_type=f"structure.{event_suffix}",
            payload=payload,
            tenant_id=school_id,
            user_id=user_id,
        )
    except Exception as exc:
        logger.warning(
            "structure_event_publish_skipped",
            event_suffix=event_suffix,
            error=str(exc),
        )
