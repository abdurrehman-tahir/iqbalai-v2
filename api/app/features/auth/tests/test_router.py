"""API contract tests for the server-side OIDC flow — T-244 (ARCH §6.4).

Per the ticket's own test requirement, the Authentik token endpoint is faked
only at the HTTP boundary (``exchange_code_for_token`` / ``exchange_refresh_token``
are monkeypatched) — state/nonce/PKCE storage runs for real against a fake
in-memory Redis, and cookie-attribute assertions are explicit (this is the C1
fix: prove HttpOnly/Secure/SameSite=Lax/Max-Age, don't just assert 200).
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.v1.router import router as v1_router
from app.core.dependencies import get_db
from app.core.exceptions import setup_exception_handlers
from app.features.auth import oidc_session as oidc_session_module
from app.features.auth import refresh_session as refresh_session_module


class _FakeRedis:
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
def fake_redis(monkeypatch: pytest.MonkeyPatch) -> _FakeRedis:
    redis = _FakeRedis()
    monkeypatch.setattr(oidc_session_module, "get_redis", lambda: redis)
    monkeypatch.setattr(refresh_session_module, "get_redis", lambda: redis)
    return redis


def _build_client() -> AsyncClient:
    app = FastAPI()
    app.include_router(v1_router, prefix="/api/v1")
    setup_exception_handlers(app)

    async def _override_db() -> AsyncGenerator[None, None]:
        yield None

    app.dependency_overrides[get_db] = _override_db
    return AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver", follow_redirects=False
    )


# ---------------------------------------------------------------------------
# GET /auth/login
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_login_redirects_to_authorize_with_pkce_state_nonce(
    fake_redis: _FakeRedis,
) -> None:
    async with _build_client() as client:
        resp = await client.get("/api/v1/auth/login")

    assert resp.status_code == 302
    location = urlparse(resp.headers["location"])
    params = parse_qs(location.query)

    assert params["response_type"] == ["code"]
    assert params["code_challenge_method"] == ["S256"]
    assert "code_challenge" in params
    assert "state" in params
    assert "nonce" in params
    assert "redirect_uri" in params


@pytest.mark.asyncio
async def test_login_sets_httponly_transient_session_cookie(fake_redis: _FakeRedis) -> None:
    async with _build_client() as client:
        resp = await client.get("/api/v1/auth/login")

    set_cookie = resp.headers.get("set-cookie", "")
    assert "iqbalai_oidc_session=" in set_cookie
    assert "httponly" in set_cookie.lower()
    assert "samesite=lax" in set_cookie.lower()


@pytest.mark.asyncio
async def test_login_stores_matching_state_in_redis(fake_redis: _FakeRedis) -> None:
    async with _build_client() as client:
        resp = await client.get("/api/v1/auth/login")

    location_state = parse_qs(urlparse(resp.headers["location"]).query)["state"][0]
    # Exactly one oidc_session:* entry should exist, holding this same state.
    stored_values = list(fake_redis.store.values())
    assert len(stored_values) == 1
    assert location_state in stored_values[0]


# ---------------------------------------------------------------------------
# GET /auth/callback — rejections
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_callback_missing_state_is_rejected(fake_redis: _FakeRedis) -> None:
    async with _build_client() as client:
        resp = await client.get("/api/v1/auth/callback", params={"code": "abc"})

    assert resp.status_code == 302
    assert "/login" in resp.headers["location"]
    assert "error=" in resp.headers["location"]


@pytest.mark.asyncio
async def test_callback_wrong_state_is_rejected(fake_redis: _FakeRedis) -> None:
    async with _build_client() as client:
        login_resp = await client.get("/api/v1/auth/login")
        session_cookie = login_resp.cookies.get("iqbalai_oidc_session")
        assert session_cookie

        client.cookies.set("iqbalai_oidc_session", session_cookie)
        resp = await client.get(
            "/api/v1/auth/callback", params={"code": "abc", "state": "tampered-state"}
        )

    assert resp.status_code == 302
    assert "/login" in resp.headers["location"]


@pytest.mark.asyncio
async def test_callback_missing_session_cookie_is_rejected(fake_redis: _FakeRedis) -> None:
    async with _build_client() as client:
        resp = await client.get(
            "/api/v1/auth/callback", params={"code": "abc", "state": "some-state"}
        )

    assert resp.status_code == 302
    assert "/login" in resp.headers["location"]


@pytest.mark.asyncio
async def test_callback_authentik_error_param_is_rejected(fake_redis: _FakeRedis) -> None:
    async with _build_client() as client:
        resp = await client.get("/api/v1/auth/callback", params={"error": "access_denied"})

    assert resp.status_code == 302
    assert "/login" in resp.headers["location"]


@pytest.mark.asyncio
async def test_callback_wrong_nonce_is_rejected(
    fake_redis: _FakeRedis, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def _fake_exchange(**kwargs: Any) -> dict[str, Any]:
        return {"id_token": "fake", "access_token": "fake-access"}

    async def _fake_decode(token: str) -> dict[str, object]:
        return {"sub": "u-1", "nonce": "wrong-nonce", "role": "teacher"}

    monkeypatch.setattr("app.features.auth.router.exchange_code_for_token", _fake_exchange)
    monkeypatch.setattr("app.features.auth.router.decode_jwt", _fake_decode)

    async with _build_client() as client:
        login_resp = await client.get("/api/v1/auth/login")
        session_cookie = login_resp.cookies.get("iqbalai_oidc_session")
        assert session_cookie
        real_state = parse_qs(urlparse(login_resp.headers["location"]).query)["state"][0]

        client.cookies.set("iqbalai_oidc_session", session_cookie)
        resp = await client.get(
            "/api/v1/auth/callback", params={"code": "abc", "state": real_state}
        )

    assert resp.status_code == 302
    assert "/login" in resp.headers["location"]


# ---------------------------------------------------------------------------
# GET /auth/callback — happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_callback_happy_path_sets_both_cookies_with_locked_attributes(
    fake_redis: _FakeRedis, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured_nonce: dict[str, str] = {}

    async def _fake_exchange(*, code: str, code_verifier: str, redirect_uri: str) -> dict[str, Any]:
        return {
            "id_token": "fake-id-token",
            "access_token": "fake-access-token",
            "refresh_token": "fake-refresh-token",
        }

    async def _fake_decode(token: str) -> dict[str, object]:
        return {"sub": "authentik-u1", "nonce": captured_nonce["value"], "role": "teacher"}

    async def _fake_post_login(self: Any, claims: dict[str, object]) -> dict[str, object]:
        return {
            "user_id": "u-1",
            "role": "teacher",
            "tos_acceptance_required": False,
            "is_first_login": False,
        }

    monkeypatch.setattr("app.features.auth.router.exchange_code_for_token", _fake_exchange)
    monkeypatch.setattr("app.features.auth.router.decode_jwt", _fake_decode)
    monkeypatch.setattr("app.features.auth.service.AuthService.post_login", _fake_post_login)

    async with _build_client() as client:
        login_resp = await client.get("/api/v1/auth/login")
        session_cookie = login_resp.cookies.get("iqbalai_oidc_session")
        assert session_cookie
        real_state = parse_qs(urlparse(login_resp.headers["location"]).query)["state"][0]
        real_nonce = parse_qs(urlparse(login_resp.headers["location"]).query)["nonce"][0]
        captured_nonce["value"] = real_nonce

        client.cookies.set("iqbalai_oidc_session", session_cookie)
        resp = await client.get(
            "/api/v1/auth/callback", params={"code": "abc", "state": real_state}
        )

    assert resp.status_code == 302
    assert resp.headers["location"].endswith("/teacher")

    set_cookie_headers = resp.headers.get_list("set-cookie")
    access_cookie = next(c for c in set_cookie_headers if c.startswith("iqbalai_access="))
    refresh_cookie = next(c for c in set_cookie_headers if c.startswith("iqbalai_refresh="))

    for cookie_header, max_age in (
        (access_cookie, 24 * 60 * 60),
        (refresh_cookie, 30 * 24 * 60 * 60),
    ):
        lowered = cookie_header.lower()
        assert "httponly" in lowered
        assert "samesite=lax" in lowered
        assert f"max-age={max_age}" in lowered
        assert "path=/" in lowered
        # COOKIE_SECURE defaults True in Settings; local test env doesn't override it.
        assert "secure" in lowered


@pytest.mark.asyncio
async def test_callback_tos_required_redirects_to_tos_flag(
    fake_redis: _FakeRedis, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured_nonce: dict[str, str] = {}

    async def _fake_exchange(**kwargs: Any) -> dict[str, Any]:
        return {"id_token": "fake", "access_token": "fake-access"}

    async def _fake_decode(token: str) -> dict[str, object]:
        return {"sub": "u-1", "nonce": captured_nonce["value"], "role": "student"}

    async def _fake_post_login(self: Any, claims: dict[str, object]) -> dict[str, object]:
        return {
            "user_id": "u-1",
            "role": "student",
            "tos_acceptance_required": True,
            "is_first_login": True,
        }

    monkeypatch.setattr("app.features.auth.router.exchange_code_for_token", _fake_exchange)
    monkeypatch.setattr("app.features.auth.router.decode_jwt", _fake_decode)
    monkeypatch.setattr("app.features.auth.service.AuthService.post_login", _fake_post_login)

    async with _build_client() as client:
        login_resp = await client.get("/api/v1/auth/login")
        session_cookie = login_resp.cookies.get("iqbalai_oidc_session")
        assert session_cookie
        real_state = parse_qs(urlparse(login_resp.headers["location"]).query)["state"][0]
        captured_nonce["value"] = parse_qs(urlparse(login_resp.headers["location"]).query)["nonce"][
            0
        ]

        client.cookies.set("iqbalai_oidc_session", session_cookie)
        resp = await client.get(
            "/api/v1/auth/callback", params={"code": "abc", "state": real_state}
        )

    assert resp.status_code == 302
    assert "tos_required=1" in resp.headers["location"]


# ---------------------------------------------------------------------------
# POST /auth/refresh
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_refresh_without_cookie_returns_401(fake_redis: _FakeRedis) -> None:
    async with _build_client() as client:
        resp = await client.post("/api/v1/auth/refresh")

    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh_with_unknown_reference_returns_401(fake_redis: _FakeRedis) -> None:
    async with _build_client() as client:
        client.cookies.set("iqbalai_refresh", "never-issued-reference")
        resp = await client.post("/api/v1/auth/refresh")

    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh_rotates_access_and_refresh_cookies(
    fake_redis: _FakeRedis, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.features.auth.refresh_session import store_refresh_token

    async def _fake_exchange_refresh(refresh_token: str) -> dict[str, Any]:
        assert refresh_token == "real-authentik-refresh-token"
        return {"access_token": "new-access-token", "refresh_token": "new-real-refresh-token"}

    monkeypatch.setattr("app.features.auth.router.exchange_refresh_token", _fake_exchange_refresh)

    opaque_ref = await store_refresh_token("real-authentik-refresh-token")

    async with _build_client() as client:
        client.cookies.set("iqbalai_refresh", opaque_ref)
        resp = await client.post("/api/v1/auth/refresh")

    assert resp.status_code == 204
    set_cookie_headers = resp.headers.get_list("set-cookie")
    access_cookie = next(c for c in set_cookie_headers if c.startswith("iqbalai_access="))
    new_refresh_cookie = next(c for c in set_cookie_headers if c.startswith("iqbalai_refresh="))

    assert "new-access-token" in access_cookie
    # The cookie now carries a NEW opaque reference, never the raw new refresh token.
    assert "new-real-refresh-token" not in new_refresh_cookie
    assert opaque_ref not in new_refresh_cookie

    # Old reference is now dead (rotation, single-use).
    assert opaque_ref not in fake_redis.store
