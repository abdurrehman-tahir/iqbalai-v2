"""Dead-letter queue helpers for Celery tasks — ARCH §10.11."""

from __future__ import annotations

import json
from typing import Any

import structlog
from redis import Redis

from app.config import get_settings

logger = structlog.get_logger(__name__)


def push_task_dlq(task_name: str, payload: dict[str, Any], error: str) -> None:
    """Push a terminal task failure to the Redis DLQ list for manual inspection."""
    entry = {
        "task_name": task_name,
        "payload": payload,
        "error": error[:2000],
    }
    client = Redis.from_url(get_settings().REDIS_URL)
    client.lpush(f"dlq:{task_name}", json.dumps(entry))
    logger.error(
        "task_dlq_enqueued",
        task_name=task_name,
        payload=payload,
        error=error[:500],
    )
