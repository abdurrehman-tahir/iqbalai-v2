"""Tests for AuthMiddleware per T-006 acceptance criteria."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from app.core.middleware import PUBLIC_PATHS, TOS_ALLOWED_PATHS, AuthMiddleware
from app.features.users.models import User, UserAccountStatus, UserRole


def _echo_claims(request: Request) -> JSONResponse:
    """Test endpoint that returns whatever claims were set on state."""
    claims = getattr(request.state, "claims", None)
    return JSONResponse({"claims": claims})


def _make_test_app() -> Starlette:
    app = Starlette(
        routes=[
            Route("/secret", _echo_claims, methods=["GET", "POST"]),
            Route("/health", _echo_claims),
            Route("/api/v1/users/me/accept-tos", _echo_claims, methods=["POST"]),
            Route("/api/v1/independent/signup", _echo_claims, methods=["POST"]),
        ]
    )
    app.add_middleware(AuthMiddleware)
    return app


@pytest.fixture()
def client() -> TestClient:
    return TestClient(_make_test_app(), raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# PUBLIC_PATHS sanity checks
# ---------------------------------------------------------------------------


def test_public_paths_includes_health() -> None:
    assert "/health" in PUBLIC_PATHS


def test_public_paths_includes_metrics() -> None:
    assert "/metrics" in PUBLIC_PATHS


def test_public_paths_includes_auth_callback() -> None:
    assert "/api/v1/auth/callback" in PUBLIC_PATHS


def test_public_paths_is_exactly_the_locked_allowlist() -> None:
    """T-238: PUBLIC_PATHS is a small allowlist (auth/health/docs) — nothing else.

    A `/me/`-style feature route is never a legitimate PUBLIC_PATHS entry (a `/me/`
    endpoint can't resolve a user without auth — see the M-05 exam-frameworks bypass
    this test guards against). Any future addition must be justified in review, not
    grown ad hoc.

    T-244 justification for `/api/v1/auth/refresh`: it's called precisely when
    the access token is expired/missing, so it can't require one itself — it
    validates the iqbalai_refresh cookie internally instead (ARCH §6.9).
    """
    assert PUBLIC_PATHS == frozenset(
        {
            "/health",
            "/health/ready",
            "/api/v1/health",
            "/api/v1/health/ready",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/api/v1/auth/callback",
            "/api/v1/auth/login",
            "/api/v1/auth/refresh",
            "/api/v1/auth/accept-invite",
            "/api/v1/independent/signup",
            "/api/v1/parents/signup",
            "/metrics",
        }
    )


# ---------------------------------------------------------------------------
# Public path — no auth required
# ---------------------------------------------------------------------------


def test_public_path_returns_200_without_token(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200


def test_options_request_bypasses_auth(client: TestClient) -> None:
    response = client.options("/secret")
    assert response.status_code != 401


# ---------------------------------------------------------------------------
# Protected path — missing / rejected credential
# ---------------------------------------------------------------------------


def test_missing_cookie_returns_401(client: TestClient) -> None:
    response = client.get("/secret")
    assert response.status_code == 401


def test_authorization_header_alone_no_longer_works(client: TestClient) -> None:
    """T-245: the Bearer-header fallback T-244 kept for one milestone is gone
    — only the iqbalai_access cookie is accepted now (ARCH §6.6/§6.17)."""
    with patch(
        "app.core.middleware.decode_jwt",
        new_callable=AsyncMock,
        return_value={"sub": "user-123", "role": "teacher"},
    ):
        response = client.get("/secret", headers={"Authorization": "Bearer valid.token.here"})
    assert response.status_code == 401


def test_401_body_has_authentication_required_code(client: TestClient) -> None:
    response = client.get("/secret")
    body = response.json()
    assert body["error"]["code"] == "AUTHENTICATION_REQUIRED"


# ---------------------------------------------------------------------------
# Protected path — invalid / expired token
# ---------------------------------------------------------------------------


def test_invalid_token_returns_401(client: TestClient) -> None:
    with patch("app.core.middleware.decode_jwt", new_callable=AsyncMock, return_value=None):
        response = client.get("/secret", cookies={"iqbalai_access": "bad.token.here"})
    assert response.status_code == 401


def test_invalid_token_body_has_error_code(client: TestClient) -> None:
    with patch("app.core.middleware.decode_jwt", new_callable=AsyncMock, return_value=None):
        response = client.get("/secret", cookies={"iqbalai_access": "bad.token.here"})
    assert response.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"


# ---------------------------------------------------------------------------
# Protected path — valid token
# ---------------------------------------------------------------------------


def _db_user(**overrides: object) -> User:
    user = User(
        id="user-db-1",
        authentik_id="user-123",
        email="admin@district.edu",
        display_name="District Admin",
        role=UserRole.DISTRICT_ADMIN,
        status=UserAccountStatus.ACTIVE,
        district_id="district-abc",
    )
    for key, value in overrides.items():
        setattr(user, key, value)
    return user


def test_valid_token_passes_through(client: TestClient) -> None:
    fake_claims = {"sub": "user-123", "role": "teacher", "email": "t@school.pk"}
    with patch("app.core.middleware.decode_jwt", new_callable=AsyncMock, return_value=fake_claims):
        with patch(
            "app.core.middleware._resolve_active_user",
            new_callable=AsyncMock,
            return_value=_db_user(),
        ):
            response = client.get("/secret", cookies={"iqbalai_access": "valid.token.here"})
    assert response.status_code == 200


def test_valid_token_claims_enriched_from_database(client: TestClient) -> None:
    fake_claims = {"sub": "user-123", "role": "student", "email": "admin@district.edu"}
    with patch("app.core.middleware.decode_jwt", new_callable=AsyncMock, return_value=fake_claims):
        with patch(
            "app.core.middleware._resolve_active_user",
            new_callable=AsyncMock,
            return_value=_db_user(),
        ):
            response = client.get("/secret", cookies={"iqbalai_access": "valid.token.here"})
    body = response.json()
    assert body["claims"]["sub"] == "user-123"
    assert body["claims"]["role"] == "district_admin"
    assert body["claims"]["district_id"] == "district-abc"
    assert body["claims"]["user_id"] == "user-db-1"


def test_suspended_user_returns_403(client: TestClient) -> None:
    fake_claims = {"sub": "user-123", "role": "teacher"}
    with patch("app.core.middleware.decode_jwt", new_callable=AsyncMock, return_value=fake_claims):
        with patch(
            "app.core.middleware._resolve_active_user",
            new_callable=AsyncMock,
            return_value=_db_user(status=UserAccountStatus.SUSPENDED),
        ):
            response = client.get("/secret", cookies={"iqbalai_access": "valid.token.here"})
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ACCOUNT_SUSPENDED"


# ---------------------------------------------------------------------------
# ToS acceptance gate (T-242, audit C4) — state-changing methods only
# ---------------------------------------------------------------------------


def _auth_cookies_and_mocks() -> tuple[dict[str, str], dict[str, object]]:
    return {"iqbalai_access": "valid.token.here"}, {"sub": "user-123", "role": "teacher"}


def test_post_blocked_when_tos_not_accepted(client: TestClient) -> None:
    cookies, fake_claims = _auth_cookies_and_mocks()
    with patch("app.core.middleware.decode_jwt", new_callable=AsyncMock, return_value=fake_claims):
        with patch(
            "app.core.middleware._resolve_active_user",
            new_callable=AsyncMock,
            return_value=_db_user(),
        ):
            with patch(
                "app.core.middleware._tos_acceptance_required",
                new_callable=AsyncMock,
                return_value=True,
            ):
                response = client.post("/secret", cookies=cookies)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "TOS_ACCEPTANCE_REQUIRED"


def test_get_allowed_when_tos_not_accepted(client: TestClient) -> None:
    """GET stays readable so the FE can render the modal + content."""
    cookies, fake_claims = _auth_cookies_and_mocks()
    with patch("app.core.middleware.decode_jwt", new_callable=AsyncMock, return_value=fake_claims):
        with patch(
            "app.core.middleware._resolve_active_user",
            new_callable=AsyncMock,
            return_value=_db_user(),
        ):
            with patch(
                "app.core.middleware._tos_acceptance_required",
                new_callable=AsyncMock,
                return_value=True,
            ):
                response = client.get("/secret", cookies=cookies)
    assert response.status_code == 200


def test_post_succeeds_after_tos_accepted(client: TestClient) -> None:
    cookies, fake_claims = _auth_cookies_and_mocks()
    with patch("app.core.middleware.decode_jwt", new_callable=AsyncMock, return_value=fake_claims):
        with patch(
            "app.core.middleware._resolve_active_user",
            new_callable=AsyncMock,
            return_value=_db_user(),
        ):
            with patch(
                "app.core.middleware._tos_acceptance_required",
                new_callable=AsyncMock,
                return_value=False,
            ):
                response = client.post("/secret", cookies=cookies)
    assert response.status_code == 200


def test_accept_tos_endpoint_reachable_despite_gate(client: TestClient) -> None:
    """The accept-tos POST itself must never be blocked by its own gate."""
    assert "/api/v1/users/me/accept-tos" in TOS_ALLOWED_PATHS
    cookies, fake_claims = _auth_cookies_and_mocks()
    with patch("app.core.middleware.decode_jwt", new_callable=AsyncMock, return_value=fake_claims):
        with patch(
            "app.core.middleware._resolve_active_user",
            new_callable=AsyncMock,
            return_value=_db_user(),
        ):
            with patch(
                "app.core.middleware._tos_acceptance_required",
                new_callable=AsyncMock,
                return_value=True,
            ) as tos_check:
                response = client.post("/api/v1/users/me/accept-tos", cookies=cookies)
    assert response.status_code == 200
    tos_check.assert_not_called()


def test_suspended_user_still_blocked_before_tos_check(client: TestClient) -> None:
    """Decline path (suspended) is unchanged — account-status block runs first."""
    cookies, fake_claims = _auth_cookies_and_mocks()
    with patch("app.core.middleware.decode_jwt", new_callable=AsyncMock, return_value=fake_claims):
        with patch(
            "app.core.middleware._resolve_active_user",
            new_callable=AsyncMock,
            return_value=_db_user(status=UserAccountStatus.SUSPENDED),
        ):
            response = client.post("/secret", cookies=cookies)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ACCOUNT_SUSPENDED"


# ---------------------------------------------------------------------------
# Origin/Referer CSRF check on mutating methods (T-244, ARCH §6.17)
# ---------------------------------------------------------------------------

_ALLOWED_ORIGIN = "http://localhost:3000"


def test_cross_origin_post_is_rejected(client: TestClient) -> None:
    response = client.post("/secret", headers={"Origin": "http://evil.example"})
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ORIGIN_NOT_ALLOWED"


def test_cross_origin_post_with_valid_cookie_is_still_rejected(client: TestClient) -> None:
    """T-244 acceptance item 3, verbatim: a cross-origin mutating request is
    rejected even when it carries a legitimate, currently-valid session cookie
    — the Origin check runs before auth is even evaluated, so a stolen/replayed
    valid cookie used from a forged cross-site request still doesn't get in."""
    with patch(
        "app.core.middleware.decode_jwt",
        new_callable=AsyncMock,
        return_value={"sub": "u-1", "role": "teacher"},
    ):
        with patch(
            "app.core.middleware._resolve_active_user",
            new_callable=AsyncMock,
            return_value=_db_user(),
        ):
            response = client.post(
                "/secret",
                headers={"Origin": "http://evil.example"},
                cookies={"iqbalai_access": "valid.token.here"},
            )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ORIGIN_NOT_ALLOWED"


def test_same_origin_post_passes_the_csrf_check(client: TestClient) -> None:
    """Origin matches — request proceeds to the normal auth gate (401, no token)."""
    response = client.post("/secret", headers={"Origin": _ALLOWED_ORIGIN})
    assert response.status_code == 401  # past the CSRF check, blocked on auth instead
    assert response.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"


def test_post_with_no_origin_or_referer_is_not_csrf_blocked(client: TestClient) -> None:
    """Non-browser clients (tests, curl, tooling) send neither header — unaffected."""
    response = client.post("/secret")
    assert response.status_code == 401  # past the CSRF check
    assert response.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"


def test_referer_fallback_when_origin_absent_matching(client: TestClient) -> None:
    response = client.post("/secret", headers={"Referer": f"{_ALLOWED_ORIGIN}/some/page"})
    assert response.status_code == 401  # past the CSRF check


def test_referer_fallback_when_origin_absent_mismatched(client: TestClient) -> None:
    response = client.post("/secret", headers={"Referer": "http://evil.example/some/page"})
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ORIGIN_NOT_ALLOWED"


def test_origin_header_wins_over_a_mismatched_referer(client: TestClient) -> None:
    """Origin is authoritative when present — Referer is only a fallback."""
    response = client.post(
        "/secret",
        headers={"Origin": _ALLOWED_ORIGIN, "Referer": "http://evil.example/x"},
    )
    assert response.status_code == 401  # past the CSRF check


def test_get_requests_are_never_csrf_checked(client: TestClient) -> None:
    response = client.get("/secret", headers={"Origin": "http://evil.example"})
    assert response.status_code == 401  # 401 (no token), not 403 ORIGIN_NOT_ALLOWED


def test_csrf_check_applies_even_to_public_paths(client: TestClient) -> None:
    """Origin validity doesn't depend on whether the endpoint needs a token —
    a public signup endpoint is just as forgeable cross-site as any other."""
    assert "/api/v1/independent/signup" in PUBLIC_PATHS
    response = client.post("/api/v1/independent/signup", headers={"Origin": "http://evil.example"})
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ORIGIN_NOT_ALLOWED"


def test_csrf_check_allows_public_path_with_matching_origin(client: TestClient) -> None:
    response = client.post("/api/v1/independent/signup", headers={"Origin": _ALLOWED_ORIGIN})
    assert response.status_code == 200  # public path, valid origin — reaches the handler
