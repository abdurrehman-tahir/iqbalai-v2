"""Tests for the opaque refresh-token reference storage — T-244."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.features.auth.refresh_session import resolve_and_rotate, store_refresh_token


class _FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    async def set(self, key: str, value: str, ex: int | None = None) -> bool:
        self.store[key] = value
        return True

    async def get(self, key: str) -> str | None:
        return self.store.get(key)

    async def delete(self, key: str) -> int:
        return 1 if self.store.pop(key, None) is not None else 0


@pytest.fixture()
def fake_redis() -> _FakeRedis:
    return _FakeRedis()


@pytest.mark.asyncio
async def test_store_then_resolve_round_trips(fake_redis: _FakeRedis) -> None:
    with patch("app.features.auth.refresh_session.get_redis", return_value=fake_redis):
        opaque_ref = await store_refresh_token("real-authentik-refresh-token")
        resolved = await resolve_and_rotate(opaque_ref)

    assert resolved == "real-authentik-refresh-token"


@pytest.mark.asyncio
async def test_resolve_is_single_use(fake_redis: _FakeRedis) -> None:
    """A replayed opaque reference must fail — that's the rotation guarantee."""
    with patch("app.features.auth.refresh_session.get_redis", return_value=fake_redis):
        opaque_ref = await store_refresh_token("real-token")
        first = await resolve_and_rotate(opaque_ref)
        second = await resolve_and_rotate(opaque_ref)

    assert first == "real-token"
    assert second is None


@pytest.mark.asyncio
async def test_resolve_unknown_reference_returns_none(fake_redis: _FakeRedis) -> None:
    with patch("app.features.auth.refresh_session.get_redis", return_value=fake_redis):
        result = await resolve_and_rotate("never-issued")
    assert result is None


@pytest.mark.asyncio
async def test_opaque_reference_never_equals_the_real_token(fake_redis: _FakeRedis) -> None:
    with patch("app.features.auth.refresh_session.get_redis", return_value=fake_redis):
        opaque_ref = await store_refresh_token("super-secret-authentik-token")
    assert opaque_ref != "super-secret-authentik-token"


@pytest.mark.asyncio
async def test_rotation_issues_a_fresh_reference(fake_redis: _FakeRedis) -> None:
    with patch("app.features.auth.refresh_session.get_redis", return_value=fake_redis):
        ref_1 = await store_refresh_token("token-v1")
        await resolve_and_rotate(ref_1)
        ref_2 = await store_refresh_token("token-v2")

    assert ref_1 != ref_2
