"""Lecture generation token buffer unit tests — T-117.

A fake in-memory Redis stands in for the real client; `publish` is spied on
separately since these tests care about buffer state, not fan-out.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.features.lectures import generation_stream


class FakeRedis:
    """Minimal async Redis supporting the list/hash subset `generation_stream.py` uses."""

    def __init__(self) -> None:
        self.lists: dict[str, list[str]] = {}
        self.hashes: dict[str, dict[str, str]] = {}
        self.ttls: dict[str, int] = {}

    async def rpush(self, key: str, value: str) -> int:
        self.lists.setdefault(key, []).append(value)
        return len(self.lists[key])

    async def lrange(self, key: str, start: int, end: int) -> list[str]:
        values = self.lists.get(key, [])
        if end == -1:
            return values[start:]
        return values[start : end + 1]

    async def llen(self, key: str) -> int:
        return len(self.lists.get(key, []))

    async def expire(self, key: str, seconds: int) -> bool:
        self.ttls[key] = seconds
        return True

    async def hset(self, key: str, mapping: dict[str, str]) -> int:
        self.hashes.setdefault(key, {}).update(mapping)
        return len(mapping)

    async def hgetall(self, key: str) -> dict[str, str]:
        return dict(self.hashes.get(key, {}))


@pytest.fixture
def fake_redis(monkeypatch: pytest.MonkeyPatch) -> FakeRedis:
    redis = FakeRedis()
    monkeypatch.setattr("app.features.lectures.generation_stream.get_redis", lambda: redis)
    return redis


@pytest.fixture
def published(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, dict[str, Any]]]:
    events: list[tuple[str, dict[str, Any]]] = []

    async def _fake_publish(channel: str, message: dict[str, Any]) -> None:
        events.append((channel, message))

    monkeypatch.setattr("app.features.lectures.generation_stream.publish", _fake_publish)
    return events


@pytest.mark.asyncio
async def test_append_token_returns_incrementing_seq(
    fake_redis: FakeRedis, published: list[tuple[str, dict[str, Any]]]
) -> None:
    seq1 = await generation_stream.append_token("lec-1", "Hello")
    seq2 = await generation_stream.append_token("lec-1", " world")

    assert (seq1, seq2) == (1, 2)
    assert fake_redis.lists["lecture:gen:tokens:lec-1"] == ["Hello", " world"]
    assert fake_redis.ttls["lecture:gen:tokens:lec-1"] == generation_stream.BUFFER_TTL_SECONDS


@pytest.mark.asyncio
async def test_append_token_publishes_notice(
    fake_redis: FakeRedis, published: list[tuple[str, dict[str, Any]]]
) -> None:
    await generation_stream.append_token("lec-1", "Hello")

    channel, message = published[0]
    assert channel == "ws:lecture:lec-1"
    assert message == {"kind": "token", "seq": 1, "token": "Hello"}


@pytest.mark.asyncio
async def test_get_tokens_from_returns_only_newer_tokens(
    fake_redis: FakeRedis, published: list[tuple[str, dict[str, Any]]]
) -> None:
    for token in ["A", "B", "C"]:
        await generation_stream.append_token("lec-1", token)

    assert await generation_stream.get_tokens_from("lec-1", 0) == ["A", "B", "C"]
    assert await generation_stream.get_tokens_from("lec-1", 1) == ["B", "C"]
    assert await generation_stream.get_tokens_from("lec-1", 3) == []


@pytest.mark.asyncio
async def test_mark_complete_sets_status_and_publishes(
    fake_redis: FakeRedis, published: list[tuple[str, dict[str, Any]]]
) -> None:
    await generation_stream.mark_complete("lec-1", version_id="ver-1")

    status = await generation_stream.get_status("lec-1")
    assert status == {"status": "complete", "version_id": "ver-1"}
    channel, message = published[0]
    assert channel == "ws:lecture:lec-1"
    assert message == {"kind": "complete", "version_id": "ver-1", "status": "ready_for_edit"}


@pytest.mark.asyncio
async def test_mark_failed_sets_status_and_publishes(
    fake_redis: FakeRedis, published: list[tuple[str, dict[str, Any]]]
) -> None:
    await generation_stream.mark_failed("lec-1", reason="timed_out")

    status = await generation_stream.get_status("lec-1")
    assert status == {"status": "failed", "reason": "timed_out"}
    channel, message = published[0]
    assert channel == "ws:lecture:lec-1"
    assert message == {"kind": "error", "reason": "timed_out"}


@pytest.mark.asyncio
async def test_get_status_returns_none_when_nothing_recorded(fake_redis: FakeRedis) -> None:
    assert await generation_stream.get_status("lec-unknown") is None
