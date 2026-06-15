"""Unit tests for the Idempotency-Key support — T-029 / ARCH §5.9.

Covers the three contract behaviours: first-use claims the key, a replay with the
same body is flagged (and the cached response is returned), and reuse with a
different body raises 409. A fake in-memory Redis stands in for the real client.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.core.exceptions import IdempotencyKeyMismatchError
from app.core.idempotency import (
    _TTL_SECONDS,
    IdempotencyContext,
    idempotency_key,
)


class FakeRedis:
    """Minimal async Redis supporting the get / set(nx, ex) subset we use."""

    def __init__(self) -> None:
        self.store: dict[str, str] = {}
        self.ttls: dict[str, int | None] = {}

    async def set(
        self, key: str, value: str, ex: int | None = None, nx: bool = False
    ) -> bool | None:
        if nx and key in self.store:
            return None
        self.store[key] = value
        self.ttls[key] = ex
        return True

    async def get(self, key: str) -> str | None:
        return self.store.get(key)

    async def incr(self, key: str) -> int:
        current = int(self.store.get(key, "0"))
        current += 1
        self.store[key] = str(current)
        return current

    async def expire(self, key: str, seconds: int) -> bool:
        self.ttls[key] = seconds
        return True


@pytest.fixture
def fake_redis(monkeypatch: pytest.MonkeyPatch) -> FakeRedis:
    redis = FakeRedis()
    monkeypatch.setattr("app.core.idempotency.get_redis", lambda: redis)
    return redis


async def test_begin_first_use_claims_key(fake_redis: FakeRedis) -> None:
    ctx = IdempotencyContext(namespace_key="t1:key-1", body_hash="hashA")
    await ctx.begin()
    assert ctx.is_replay is False
    # The hash guard is stored with the 24h TTL.
    assert fake_redis.store["idem:hash:t1:key-1"] == "hashA"
    assert fake_redis.ttls["idem:hash:t1:key-1"] == _TTL_SECONDS


async def test_begin_same_body_is_replay(fake_redis: FakeRedis) -> None:
    ctx1 = IdempotencyContext(namespace_key="t1:key-1", body_hash="hashA")
    await ctx1.begin()
    ctx2 = IdempotencyContext(namespace_key="t1:key-1", body_hash="hashA")
    await ctx2.begin()
    assert ctx2.is_replay is True


async def test_begin_different_body_raises_mismatch(fake_redis: FakeRedis) -> None:
    ctx1 = IdempotencyContext(namespace_key="t1:key-1", body_hash="hashA")
    await ctx1.begin()
    ctx2 = IdempotencyContext(namespace_key="t1:key-1", body_hash="hashB")
    with pytest.raises(IdempotencyKeyMismatchError):
        await ctx2.begin()


async def test_response_cache_roundtrip(fake_redis: FakeRedis) -> None:
    ctx = IdempotencyContext(namespace_key="t1:key-1", body_hash="hashA")
    await ctx.begin()
    assert await ctx.cached_response() is None
    await ctx.store_response({"data": {"id": "d-1"}, "message": "ok"})
    cached = await ctx.cached_response()
    assert cached == {"data": {"id": "d-1"}, "message": "ok"}
    assert fake_redis.ttls["idem:resp:t1:key-1"] == _TTL_SECONDS


async def test_tenant_namespacing_isolates_same_key(fake_redis: FakeRedis) -> None:
    """The same client key in two tenants does not collide."""
    a = IdempotencyContext(namespace_key="tenantA:key-1", body_hash="hashA")
    await a.begin()
    b = IdempotencyContext(namespace_key="tenantB:key-1", body_hash="hashB")
    await b.begin()  # must NOT raise — different namespace
    assert b.is_replay is False


class _FakeRequest:
    """Stand-in for starlette Request exposing only headers + body()."""

    def __init__(self, headers: dict[str, str], body: bytes) -> None:
        self.headers = headers
        self._body = body

    async def body(self) -> bytes:
        return self._body


async def test_dependency_returns_none_without_header(fake_redis: FakeRedis) -> None:
    req: Any = _FakeRequest(headers={}, body=b"{}")
    ctx = await idempotency_key(req, claims={"sub": "u1", "tenant_id": "t1"})
    assert ctx is None


async def test_dependency_builds_context_with_header(fake_redis: FakeRedis) -> None:
    req: Any = _FakeRequest(headers={"Idempotency-Key": "abc"}, body=b'{"name":"x"}')
    ctx = await idempotency_key(req, claims={"sub": "u1", "tenant_id": "t1"})
    assert ctx is not None
    assert ctx.is_replay is False
