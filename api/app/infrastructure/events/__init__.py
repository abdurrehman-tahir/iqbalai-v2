"""NATS lifecycle helpers — eager connect guarded by EVENTS_ENABLED (T-236)."""

from __future__ import annotations

import structlog

logger = structlog.get_logger(__name__)

_nc = None


async def init_nats() -> None:
    """Connect to NATS at startup when events are enabled."""
    global _nc
    from app.config import get_settings

    settings = get_settings()
    if not settings.EVENTS_ENABLED:
        logger.info("nats_init_skipped", reason="EVENTS_ENABLED=false")
        return

    import nats

    _nc = await nats.connect(settings.NATS_URL)
    logger.info("nats_connected", url=settings.NATS_URL)


async def close_nats() -> None:
    """Close the shared NATS connection on shutdown."""
    global _nc
    if _nc is None:
        return
    await _nc.close()
    _nc = None
    logger.info("nats_closed")
