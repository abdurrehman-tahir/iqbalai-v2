"""Redis pub/sub fan-out for WebSocket delivery — ARCH §9.12/§9.13.

Channel taxonomy is locked (§9.12): `ws:<scope>:<id>`, always tenant-scoped.
Raw `redis.asyncio` stays behind `app.infrastructure.cache.client.get_redis`
(the single chokepoint) — this module never imports it directly.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import structlog

from app.infrastructure.cache.client import get_redis

logger = structlog.get_logger(__name__)


def lecture_channel(lecture_id: str) -> str:
    """`ws:lecture:<lecture_id>` per the locked taxonomy (§9.12)."""
    return f"ws:lecture:{lecture_id}"


async def publish(channel: str, message: dict[str, Any]) -> None:
    """Publish a message to a Redis pub/sub channel. Throwaway — no persistence."""
    await get_redis().publish(channel, json.dumps(message))


@asynccontextmanager
async def subscribe(channel: str) -> AsyncIterator[AsyncIterator[dict[str, Any]]]:
    """Subscribe to a channel; yields an async iterator of decoded messages.

    One Redis pub/sub connection per subscription (per connected WebSocket).
    Redis itself fans PUBLISH out to every subscriber across every API
    container, so this satisfies the multi-container delivery contract (§9.13)
    without a shared pattern-matching subscriber thread — each connection's
    subscription is independently scoped to exactly the channel it needs.
    """
    redis = get_redis()
    pubsub = redis.pubsub()
    await pubsub.subscribe(channel)
    try:

        async def _messages() -> AsyncIterator[dict[str, Any]]:
            async for raw in pubsub.listen():
                if raw.get("type") != "message":
                    continue
                try:
                    yield json.loads(raw["data"])
                except (json.JSONDecodeError, TypeError):
                    logger.warning("realtime_pubsub_bad_payload", channel=channel)

        yield _messages()
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.aclose()  # type: ignore[no-untyped-call]
