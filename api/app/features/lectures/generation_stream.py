"""Durable-enough token buffer for lecture generation streaming — T-117.

Redis pub/sub (`infrastructure/realtime/pubsub.py`) is throwaway: a message
published with no subscriber is lost, which is exactly wrong for "connection
drops mid-generation, reconnect resumes from current position" (flow-5 §3.2).
So the source of truth for what's been generated so far is a plain Redis list
(via the `cache` chokepoint, not pub/sub) — pub/sub is only used to wake up
currently-connected clients; a reconnecting client replays this buffer.

Ordering guarantee: the producer always RPUSHes a token (durably visible to
any subsequent LRANGE) before PUBLISHing notice of it. So a consumer that
subscribes first and only *then* reads the buffer will never observe a
pub/sub notice for a token the buffer doesn't already contain — safe to
merge backlog + live stream by sequence number without dropping or
duplicating tokens (see `ws_router.py`).
"""

from __future__ import annotations

from typing import Any

from app.infrastructure.cache.client import get_redis
from app.infrastructure.realtime.pubsub import lecture_channel, publish

# Long enough past the 5-minute soft_time_limit (tasks.py) to cover a slow
# reconnect; short enough that abandoned buffers don't linger in Redis.
BUFFER_TTL_SECONDS = 900


def _tokens_key(lecture_id: str) -> str:
    return f"lecture:gen:tokens:{lecture_id}"


def _status_key(lecture_id: str) -> str:
    return f"lecture:gen:status:{lecture_id}"


async def append_token(lecture_id: str, token: str) -> int:
    """Append a generated token to the buffer and notify subscribers. Returns its seq."""
    redis = get_redis()
    key = _tokens_key(lecture_id)
    seq = await redis.rpush(key, token)  # type: ignore[misc]
    await redis.expire(key, BUFFER_TTL_SECONDS)
    await publish(lecture_channel(lecture_id), {"kind": "token", "seq": seq, "token": token})
    return int(seq)


async def get_tokens_from(lecture_id: str, since_seq: int) -> list[str]:
    """Return tokens with seq > since_seq (buffer is 1-indexed by seq)."""
    redis = get_redis()
    tokens = await redis.lrange(_tokens_key(lecture_id), since_seq, -1)  # type: ignore[misc]
    return list(tokens)


async def mark_complete(lecture_id: str, *, version_id: str) -> None:
    """Record completion and notify subscribers. Terminal state for the buffer."""
    redis = get_redis()
    key = _status_key(lecture_id)
    await redis.hset(key, mapping={"status": "complete", "version_id": version_id})  # type: ignore[misc]
    await redis.expire(key, BUFFER_TTL_SECONDS)
    await publish(
        lecture_channel(lecture_id),
        {"kind": "complete", "version_id": version_id, "status": "ready_for_edit"},
    )


async def mark_failed(lecture_id: str, *, reason: str) -> None:
    """Record failure and notify subscribers."""
    redis = get_redis()
    key = _status_key(lecture_id)
    await redis.hset(key, mapping={"status": "failed", "reason": reason})  # type: ignore[misc]
    await redis.expire(key, BUFFER_TTL_SECONDS)
    await publish(lecture_channel(lecture_id), {"kind": "error", "reason": reason})


async def get_status(lecture_id: str) -> dict[str, Any] | None:
    """Return the last-known status hash, or None if nothing recorded (yet, or expired)."""
    redis = get_redis()
    data = await redis.hgetall(_status_key(lecture_id))  # type: ignore[misc]
    return dict(data) if data else None
