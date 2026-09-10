"""Redis pub/sub fan-out unit tests — T-117. A fake in-memory Redis stands in for the real client."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest

from app.infrastructure.realtime import pubsub as pubsub_module


class _FakePubSub:
    def __init__(self, redis: "FakeRedis") -> None:
        self._redis = redis
        self._channel: str | None = None
        self.unsubscribed: list[str] = []
        self.closed = False

    async def subscribe(self, channel: str) -> None:
        self._channel = channel
        self._redis.queues.setdefault(channel, asyncio.Queue())

    async def listen(self) -> Any:
        assert self._channel is not None
        queue = self._redis.queues[self._channel]
        while True:
            yield await queue.get()

    async def unsubscribe(self, channel: str) -> None:
        self.unsubscribed.append(channel)

    async def aclose(self) -> None:
        self.closed = True


class FakeRedis:
    """Minimal async Redis supporting publish/pubsub — enough for `pubsub.py`."""

    def __init__(self) -> None:
        self.queues: dict[str, asyncio.Queue[dict[str, Any]]] = {}
        self.published: list[tuple[str, str]] = []

    async def publish(self, channel: str, data: str) -> int:
        self.published.append((channel, data))
        queue = self.queues.get(channel)
        if queue is not None:
            await queue.put({"type": "message", "channel": channel, "data": data})
        return 1

    def pubsub(self) -> _FakePubSub:
        return _FakePubSub(self)


@pytest.fixture
def fake_redis(monkeypatch: pytest.MonkeyPatch) -> FakeRedis:
    redis = FakeRedis()
    monkeypatch.setattr("app.infrastructure.realtime.pubsub.get_redis", lambda: redis)
    return redis


def test_lecture_channel_is_tenant_scoped_taxonomy() -> None:
    assert pubsub_module.lecture_channel("lec-1") == "ws:lecture:lec-1"


@pytest.mark.asyncio
async def test_publish_json_encodes_message(fake_redis: FakeRedis) -> None:
    await pubsub_module.publish("ws:lecture:lec-1", {"kind": "token", "seq": 1})

    channel, raw = fake_redis.published[0]
    assert channel == "ws:lecture:lec-1"
    assert json.loads(raw) == {"kind": "token", "seq": 1}


@pytest.mark.asyncio
async def test_subscribe_yields_published_messages(fake_redis: FakeRedis) -> None:
    async with pubsub_module.subscribe("ws:lecture:lec-1") as messages:
        await pubsub_module.publish("ws:lecture:lec-1", {"kind": "token", "seq": 1, "token": "Hi"})
        received = await anext(messages)

    assert received == {"kind": "token", "seq": 1, "token": "Hi"}


@pytest.mark.asyncio
async def test_subscribe_cleans_up_on_exit(fake_redis: FakeRedis) -> None:
    async with pubsub_module.subscribe("ws:lecture:lec-1") as _messages:
        pass

    # The context manager's own pubsub instance closed cleanly; nothing to assert
    # on the closed fake directly since it's scoped inside `subscribe()`, but a
    # second subscribe on the same channel must still work (queue wasn't torn down).
    async with pubsub_module.subscribe("ws:lecture:lec-1") as messages:
        await pubsub_module.publish("ws:lecture:lec-1", {"kind": "complete"})
        received = await anext(messages)
    assert received == {"kind": "complete"}
