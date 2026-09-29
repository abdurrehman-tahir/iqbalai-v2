"""Start M-14 durable consumers as independent asyncio tasks (T-173 scaffolding)."""

from __future__ import annotations

import asyncio

import nats
import structlog

from app.config import get_settings
from app.infrastructure.events.consumers.analytics import run_analytics_consumer
from app.infrastructure.events.consumers.lag_monitor import ensure_lag_monitor_started
from app.infrastructure.events.consumers.live_feedback import (
    ensure_ticker_started,
    run_live_feedback_consumer,
)
from app.infrastructure.events.consumers.session_context import run_session_context_consumer
from app.infrastructure.events.streams import ensure_streams

logger = structlog.get_logger(__name__)

_TASKS: list[asyncio.Task[None]] = []


async def start_m14_consumers() -> None:
    """Ensure streams + spawn three independent durable consumers + lag monitor."""
    settings = get_settings()
    if not settings.EVENTS_ENABLED:
        logger.info("m14_consumers_skipped", reason="EVENTS_ENABLED=false")
        return

    nc = await nats.connect(settings.NATS_URL)
    try:
        await ensure_streams(nc.jetstream())
    finally:
        await nc.close()

    ensure_ticker_started()
    ensure_lag_monitor_started()

    _TASKS.extend(
        [
            asyncio.create_task(run_analytics_consumer(), name="m14-analytics"),
            asyncio.create_task(run_session_context_consumer(), name="m14-session-context"),
            asyncio.create_task(run_live_feedback_consumer(), name="m14-live-feedback"),
        ]
    )
    logger.info("m14_consumers_started", count=len(_TASKS))


async def stop_m14_consumers() -> None:
    for task in _TASKS:
        task.cancel()
    _TASKS.clear()
