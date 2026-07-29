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
from app.core.dependencies import get_current_user, get_db
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

    async def exists(self, key: str) -> int:
        return 1 if key in self.store else 0


@pytest.fixture()
def fake_redis(monkeypatch: pytest.MonkeyPatch) -> _FakeRedis:
    redis = _FakeRedis()
    monkeypatch.setattr(oidc_session_module, "get_redis", lambda: redis)
    monkeypatch.setattr(refresh_session_module, "get_redis", lambda: redis)
    return redis


def _build_client(claims: dict[str, object] | None = None) -> AsyncClient:
    app = FastAPI()
    app.include_router(v1_router, prefix="/api/v1")
    setup_exception_handlers(app)

    async def _override_db() -> AsyncGenerator[None, None]:
        yield None

    app.dependency_overrides[get_db] = _override_db
    if claims is not None:
        app.dependency_overrides[get_current_user] = lambda: claims
    return AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver", follow_redirects=False
    )


# ---------------------------------------------------------------------------
# GET /auth/me
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_me_requires_auth() -> None:
    async with _build_client() as client:
        resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_returns_enriched_claims() -> None:
    claims: dict[str, object] = {
        "sub": "authentik-1",
        "email": "t@school.pk",
        "role": "teacher",
        "user_id": "u-1",
        "tenant_type": "school",
        "district_id": "d-1",
        "school_id": "s-1",
    }
    async with _build_client(claims=claims) as client:
        resp = await client.get("/api/v1/auth/me")

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data == {
        "user_id": "u-1",
        "email": "t@school.pk",
        "role": "teacher",
        "tenant_type": "school",
        "district_id": "d-1",
        "school_id": "s-1",
    }


@pytest.mark.asyncio
async def test_me_omits_district_school_when_absent() -> None:
    claims: dict[str, object] = {
        "sub": "authentik-2",
        "email": "indep@example.com",
        "role": "independent_teacher",
        "user_id": "u-2",
        "tenant_type": "independent",
    }
    async with _build_client(claims=claims) as client:
        resp = await client.get("/api/v1/auth/me")

    data = resp.json()["data"]
    assert data["district_id"] is None
    assert data["school_id"] is None


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


@pytest.mark.asyncio
async def test_login_passes_through_prompt_and_login_hint(fake_redis: _FakeRedis) -> None:
    """Post-invite/post-signup flows force a fresh login pre-filled with the
    verified email, instead of silently reusing an unrelated SSO session."""
    async with _build_client() as client:
        resp = await client.get(
            "/api/v1/auth/login",
            params={"prompt_login": "true", "login_hint": "new-teacher@school.edu"},
        )

    params = parse_qs(urlparse(resp.headers["location"]).query)
    assert params["prompt"] == ["login"]
    assert params["login_hint"] == ["new-teacher@school.edu"]


@pytest.mark.asyncio
async def test_login_omits_prompt_and_login_hint_when_not_requested(
    fake_redis: _FakeRedis,
) -> None:
    async with _build_client() as client:
        resp = await client.get("/api/v1/auth/login")

    params = parse_qs(urlparse(resp.headers["location"]).query)
    assert "prompt" not in params
    assert "login_hint" not in params


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


# ---------------------------------------------------------------------------
# POST /auth/logout (T-246, ARCH §6.8)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_logout_with_no_cookies_still_succeeds(fake_redis: _FakeRedis) -> None:
    """Logout must always succeed, even with a dying/absent session (ARCH §6.8)."""
    async with _build_client() as client:
        resp = await client.post("/api/v1/auth/logout")

    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_logout_clears_both_session_cookies(fake_redis: _FakeRedis) -> None:
    async with _build_client() as client:
        client.cookies.set("iqbalai_access", "some.access.token")
        client.cookies.set("iqbalai_refresh", "some-opaque-ref")
        resp = await client.post("/api/v1/auth/logout")

    assert resp.status_code == 204
    set_cookie_headers = resp.headers.get_list("set-cookie")
    access_clear = next(c for c in set_cookie_headers if c.startswith("iqbalai_access="))
    refresh_clear = next(c for c in set_cookie_headers if c.startswith("iqbalai_refresh="))
    for cleared in (access_clear, refresh_clear):
        lowered = cleared.lower()
        assert "max-age=0" in lowered or "expires=thu, 01 jan 1970" in lowered


@pytest.mark.asyncio
async def test_logout_blacklists_the_access_token_jti(
    fake_redis: _FakeRedis, monkeypatch: pytest.MonkeyPatch
) -> None:
    """After logout, the same token's jti must read back as blacklisted."""
    import time as time_module

    from app.core.security import blacklist_id_for, is_jti_blacklisted

    monkeypatch.setattr("app.core.security.get_redis", lambda: fake_redis)

    async def _fake_decode(token: str) -> dict[str, object]:
        return {
            "sub": "u-1",
            "role": "teacher",
            "jti": "jti-under-test",
            "exp": time_module.time() + 3600,
        }

    monkeypatch.setattr("app.features.auth.router.decode_jwt", _fake_decode)

    async with _build_client() as client:
        client.cookies.set("iqbalai_access", "some.access.token")
        resp = await client.post("/api/v1/auth/logout")

    assert resp.status_code == 204
    claims: dict[str, object] = {"jti": "jti-under-test"}
    assert await is_jti_blacklisted(blacklist_id_for("some.access.token", claims)) is True


@pytest.mark.asyncio
async def test_logout_already_expired_access_token_does_not_error(
    fake_redis: _FakeRedis, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An expired/garbage access cookie has nothing to blacklist — logout still 204s."""
    monkeypatch.setattr("app.core.security.get_redis", lambda: fake_redis)

    async def _fake_decode(token: str) -> dict[str, object] | None:
        return None

    monkeypatch.setattr("app.features.auth.router.decode_jwt", _fake_decode)

    async with _build_client() as client:
        client.cookies.set("iqbalai_access", "garbage.token.here")
        resp = await client.post("/api/v1/auth/logout")

    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_logout_revokes_and_rotates_out_the_refresh_reference(
    fake_redis: _FakeRedis, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The opaque refresh reference must be consumed so a stolen cookie can't
    be replayed against /auth/refresh after logout."""
    from app.features.auth.refresh_session import store_refresh_token

    revoked: dict[str, str] = {}

    async def _fake_revoke(refresh_token: str) -> None:
        revoked["token"] = refresh_token

    monkeypatch.setattr("app.features.auth.router.revoke_refresh_token", _fake_revoke)

    opaque_ref = await store_refresh_token("real-authentik-refresh-token")

    async with _build_client() as client:
        client.cookies.set("iqbalai_refresh", opaque_ref)
        resp = await client.post("/api/v1/auth/logout")

    assert resp.status_code == 204
    assert revoked["token"] == "real-authentik-refresh-token"
    assert opaque_ref not in fake_redis.store


@pytest.mark.asyncio
async def test_logout_succeeds_even_when_authentik_revoke_fails(
    fake_redis: _FakeRedis, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A revoke-endpoint failure at Authentik must not block logout — our own
    state (cookies, opaque reference) is already torn down regardless."""
    from app.features.auth.oidc_client import OAuthError
    from app.features.auth.refresh_session import store_refresh_token

    async def _fake_revoke(refresh_token: str) -> None:
        raise OAuthError(error="server_error")

    monkeypatch.setattr("app.features.auth.router.revoke_refresh_token", _fake_revoke)

    opaque_ref = await store_refresh_token("real-authentik-refresh-token")

    async with _build_client() as client:
        client.cookies.set("iqbalai_refresh", opaque_ref)
        resp = await client.post("/api/v1/auth/logout")

    assert resp.status_code == 204
