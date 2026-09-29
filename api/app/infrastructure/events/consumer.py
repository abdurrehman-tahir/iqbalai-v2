"""NATS JetStream durable consumer helpers + lag tracking (T-173 / T-178)."""

from __future__ import annotations

import json
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

import nats
import structlog

from app.config import get_settings
from app.infrastructure.events.streams import ensure_streams

logger = structlog.get_logger(__name__)

Handler = Callable[[dict[str, Any]], Awaitable[None]]


@dataclass
class ConsumerLagState:
    """Per-durable-consumer lag observability (T-178)."""

    durable_name: str
    last_msg_timestamp_ms: float | None = None
    last_ack_at: float = field(default_factory=time.monotonic)
    last_lag_seconds: float = 0.0
    stalled_alert_fired: bool = False

    def observe_message(self, envelope: dict[str, Any]) -> float:
        """Update lag from envelope timestamp; return lag seconds."""
        now = time.time()
        raw = envelope.get("timestamp") or envelope.get("occurred_at")
        msg_ts = now
        if isinstance(raw, str) and raw:
            try:
                from datetime import datetime

                msg_ts = datetime.fromisoformat(raw.replace("Z", "+00:00")).timestamp()
            except ValueError:
                msg_ts = now
        self.last_msg_timestamp_ms = msg_ts * 1000.0
        lag = max(0.0, now - msg_ts)
        self.last_lag_seconds = lag
        self.last_ack_at = time.monotonic()
        return lag


# Process-wide lag registry (one entry per durable consumer).
_LAG_REGISTRY: dict[str, ConsumerLagState] = {}


def get_lag_state(durable_name: str) -> ConsumerLagState:
    state = _LAG_REGISTRY.get(durable_name)
    if state is None:
        state = ConsumerLagState(durable_name=durable_name)
        _LAG_REGISTRY[durable_name] = state
    return state


def reset_lag_registry() -> None:
    """Test helper — clear lag state between cases."""
    _LAG_REGISTRY.clear()


async def consume(
    subject: str,
    handler: Handler,
    durable_name: str | None = None,
    *,
    ensure_stream: bool = True,
) -> None:
    """Subscribe to a NATS JetStream subject and call handler for each message.

    Durable subscriptions survive restart and resume from the last ack.
    """
    settings = get_settings()
    if not settings.EVENTS_ENABLED:
        logger.info(
            "event_consumer_skipped",
            reason="EVENTS_ENABLED=false",
            subject=subject,
            durable=durable_name,
        )
        return

    nc = await nats.connect(settings.NATS_URL)
    js = nc.jetstream()
    if ensure_stream:
        await ensure_streams(js)

    lag_state = get_lag_state(durable_name or subject)

    async def _message_handler(msg: Any) -> None:
        try:
            envelope = json.loads(msg.data.decode())
            logger.debug(
                "event_received",
                subject=subject,
                durable=durable_name,
                event_type=envelope.get("event_type"),
            )
            lag_state.observe_message(envelope)
            await handler(envelope)
            await msg.ack()
        except Exception as exc:
            logger.error(
                "event_handler_failed",
                subject=subject,
                durable=durable_name,
                error=str(exc),
            )
            await msg.nak()

    sub_kwargs: dict[str, Any] = {}
    if durable_name:
        sub_kwargs["durable"] = durable_name

    await js.subscribe(subject, cb=_message_handler, **sub_kwargs)
    logger.info("event_consumer_started", subject=subject, durable=durable_name)
