"""Tests for server-side OIDC state/nonce/PKCE storage — T-244."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest

from app.features.auth.oidc_session import (
    consume_oidc_session,
    create_oidc_session,
    safe_next_path,
)


class _FakeRedis:
    """Minimal in-memory stand-in for the redis.asyncio interface used here."""

    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    async def set(self, key: str, value: str, ex: int | None = None, nx: bool = False) -> bool:
        if nx and key in self.store:
            return False
        self.store[key] = value
        return True

    async def get(self, key: str) -> str | None:
        return self.store.get(key)

    async def delete(self, key: str) -> int:
        return 1 if self.store.pop(key, None) is not None else 0


@pytest.fixture()
def fake_redis() -> _FakeRedis:
    return _FakeRedis()


def _patch_redis(fake: _FakeRedis) -> Any:
    return patch("app.features.auth.oidc_session.get_redis", return_value=fake)


@pytest.mark.asyncio
async def test_create_then_consume_round_trips(fake_redis: _FakeRedis) -> None:
    with _patch_redis(fake_redis):
        session_id, session = await create_oidc_session("/coordinator/grades")
        consumed = await consume_oidc_session(session_id)

    assert consumed is not None
    assert consumed.state == session.state
    assert consumed.nonce == session.nonce
    assert consumed.code_verifier == session.code_verifier
    assert consumed.next_path == "/coordinator/grades"


@pytest.mark.asyncio
async def test_consume_is_single_use(fake_redis: _FakeRedis) -> None:
    """A replayed callback (same session cookie) must fail, not re-run the exchange."""
    with _patch_redis(fake_redis):
        session_id, _ = await create_oidc_session("/")
        first = await consume_oidc_session(session_id)
        second = await consume_oidc_session(session_id)

    assert first is not None
    assert second is None


@pytest.mark.asyncio
async def test_consume_unknown_session_id_returns_none(fake_redis: _FakeRedis) -> None:
    with _patch_redis(fake_redis):
        result = await consume_oidc_session("never-issued")
    assert result is None


@pytest.mark.asyncio
async def test_state_and_nonce_are_unique_per_session(fake_redis: _FakeRedis) -> None:
    with _patch_redis(fake_redis):
        _, session_a = await create_oidc_session("/")
        _, session_b = await create_oidc_session("/")

    assert session_a.state != session_b.state
    assert session_a.nonce != session_b.nonce
    assert session_a.code_verifier != session_b.code_verifier


@pytest.mark.parametrize(
    ("candidate", "expected"),
    [
        ("/coordinator/grades", "/coordinator/grades"),
        ("/valid-path_123", "/valid-path_123"),
        ("//evil.com", "/default"),
        ("http://evil.com", "/default"),
        ("https://evil.com/x", "/default"),
        ("relative", "/default"),
        (None, "/default"),
        ("", "/default"),
    ],
)
def test_safe_next_path_rejects_open_redirects(candidate: str | None, expected: str) -> None:
    assert safe_next_path(candidate, default="/default") == expected
