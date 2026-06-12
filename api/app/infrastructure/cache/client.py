"""Async Redis cache client — the single chokepoint for raw redis access.

Per STACK_LOCK §3.11 and the stack-enforcer Rule 2, raw ``redis.asyncio`` may only
be imported inside ``app/infrastructure/cache/*`` (plus the events dedup + celery
modules). Every other layer reaches Redis through the helpers exposed here, so the
connection is pooled in one place and cache keys stay tenant-aware.

The client is created lazily and cached at module scope; ``decode_responses=True``
means callers get ``str`` values back rather than ``bytes``.
"""

from __future__ import annotations

import redis.asyncio as redis
import structlog

from app.config import get_settings

logger = structlog.get_logger(__name__)

_client: redis.Redis | None = None


def get_redis() -> redis.Redis:
    """Return the process-wide async Redis client, creating it on first use."""
    global _client
    if _client is None:
        settings = get_settings()
        # redis-py ships `from_url` untyped; the returned client is correct at runtime.
        _client = redis.from_url(  # type: ignore[no-untyped-call]
            settings.REDIS_URL, decode_responses=True
        )
        logger.info("redis_client_initialised", url=settings.REDIS_URL)
    return _client


async def close_redis() -> None:
    """Close and drop the cached client (called on app shutdown / in tests)."""
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
