"""NATS JetStream event consumer helpers."""
from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from typing import Any

import nats
import structlog

from app.config import get_settings

logger = structlog.get_logger(__name__)


async def consume(
    subject: str,
    handler: Callable[[dict[str, Any]], Awaitable[None]],
    durable_name: str | None = None,
) -> None:
    """Subscribe to a NATS JetStream subject and call handler for each message.

    This is a simple consume-until-cancelled pattern. For production use,
    consumers are created per-feature with appropriate durable names.
    """
    settings = get_settings()
    nc = await nats.connect(settings.NATS_URL)
    js = nc.jetstream()

    async def _message_handler(msg: nats.aio.client.Msg) -> None:
        try:
            envelope = json.loads(msg.data.decode())
            logger.debug("event_received", subject=subject, event_type=envelope.get("event_type"))
            await handler(envelope)
            await msg.ack()
        except Exception as exc:
            logger.error("event_handler_failed", subject=subject, error=str(exc))
            await msg.nak()

    sub_kwargs: dict[str, Any] = {}
    if durable_name:
        sub_kwargs["durable"] = durable_name

    await js.subscribe(subject, cb=_message_handler, **sub_kwargs)
    logger.info("event_consumer_started", subject=subject)
