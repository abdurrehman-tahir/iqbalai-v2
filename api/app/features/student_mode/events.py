"""Best-effort NATS publish for mode.changed (flow-4 §3.4 / ARCH §9.3)."""

from __future__ import annotations

from typing import Any

import structlog

logger = structlog.get_logger(__name__)


async def publish_mode_changed(
    *,
    user_id: str,
    school_id: str,
    active_mode: str,
    previous_mode: str | None,
) -> None:
    """Publish ``mode.changed`` on the student-events stream (best-effort)."""
    payload: dict[str, Any] = {
        "active_mode": active_mode,
        "previous_mode": previous_mode,
    }
    try:
        from app.infrastructure.events.publisher import publish

        await publish(
            subject="mode.changed",
            event_type="mode.changed",
            payload=payload,
            tenant_id=school_id,
            tenant_type="school",
            user_id=user_id,
        )
    except Exception as exc:
        logger.warning(
            "mode_changed_event_publish_skipped",
            user_id=user_id,
            error=str(exc),
        )
