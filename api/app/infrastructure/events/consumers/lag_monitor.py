"""Pipeline lag monitor — stalled durable consumer → Platform Admin (T-178)."""

from __future__ import annotations

import asyncio
import time
from typing import Any

import structlog

from app.config import get_settings
from app.db.session import async_session_factory
from app.infrastructure.audit.log import audit
from app.infrastructure.events.consumer import get_lag_state
from app.infrastructure.events.publisher import publish
from app.infrastructure.events.subjects import (
    ANALYTICS_CONSUMER,
    LIVE_FEEDBACK_CONSUMER,
    SESSION_CONTEXT_CONSUMER,
    SYSTEM_EVENT_PIPELINE_LAG,
)
from app.infrastructure.notifications.system import notify_all_platform_admins

logger = structlog.get_logger(__name__)

_MONITORED = (ANALYTICS_CONSUMER, SESSION_CONTEXT_CONSUMER, LIVE_FEEDBACK_CONSUMER)
_MONITOR_TASK: asyncio.Task[None] | None = None


async def check_consumer_lag(
    durable_name: str,
    *,
    lag_seconds: float | None = None,
    force_alert: bool = False,
) -> dict[str, Any]:
    """Evaluate lag for one durable consumer; alert when threshold exceeded."""
    settings = get_settings()
    threshold = float(settings.EVENT_PIPELINE_LAG_SECONDS)
    state = get_lag_state(durable_name)
    lag = float(lag_seconds) if lag_seconds is not None else float(state.last_lag_seconds)

    # Also treat "no ack for threshold while previously active" as stalled.
    idle = time.monotonic() - state.last_ack_at
    if state.last_msg_timestamp_ms is not None and idle > threshold:
        lag = max(lag, idle)

    result = {
        "durable_name": durable_name,
        "lag_seconds": lag,
        "threshold_seconds": threshold,
        "alerted": False,
    }
    if lag <= threshold and not force_alert:
        state.stalled_alert_fired = False
        return result

    if state.stalled_alert_fired and not force_alert:
        result["alerted"] = True
        return result

    payload = {
        "durable_name": durable_name,
        "lag_seconds": lag,
        "threshold_seconds": threshold,
    }
    try:
        await publish(
            SYSTEM_EVENT_PIPELINE_LAG,
            SYSTEM_EVENT_PIPELINE_LAG,
            payload,
            tenant_id="",
            tenant_type="school",
            user_id="",
        )
    except Exception as exc:
        logger.warning("pipeline_lag_publish_failed", error=str(exc))

    async with async_session_factory() as session:
        try:
            await notify_all_platform_admins(
                session,
                template_key="system.event_pipeline_lag",
                metadata=payload,
                params={
                    "durable_name": durable_name,
                    "lag_seconds": f"{lag:.0f}",
                },
            )
            await session.commit()
        except Exception as exc:
            logger.warning("pipeline_lag_notify_failed", error=str(exc))
        try:
            from app.features.audit import actions as audit_actions

            await audit(
                session=session,
                action=audit_actions.EVENT_PIPELINE_LAG,
                actor_id=None,
                actor_role="system",
                target_type="event_consumer",
                target_id=durable_name,
                metadata=payload,
            )
        except Exception as exc:
            logger.warning("pipeline_lag_audit_failed", error=str(exc))

    state.stalled_alert_fired = True
    result["alerted"] = True
    logger.warning("event_pipeline_lag_alert", **payload)
    return result


async def _monitor_loop() -> None:
    settings = get_settings()
    interval = max(5, int(settings.EVENT_PIPELINE_LAG_CHECK_SECONDS))
    while True:
        await asyncio.sleep(interval)
        for name in _MONITORED:
            try:
                await check_consumer_lag(name)
            except Exception as exc:
                logger.warning("lag_monitor_iteration_failed", durable=name, error=str(exc))


def ensure_lag_monitor_started() -> None:
    global _MONITOR_TASK
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    if _MONITOR_TASK is None or _MONITOR_TASK.done():
        _MONITOR_TASK = loop.create_task(_monitor_loop(), name="m14-lag-monitor")


async def run_lag_monitor() -> None:
    """Long-running lag monitor (also started from consumer runner)."""
    ensure_lag_monitor_started()
    while True:
        await asyncio.sleep(3600)
