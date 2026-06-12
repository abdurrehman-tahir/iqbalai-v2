"""Tests for AuthMiddleware per T-006 acceptance criteria."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from app.core.middleware import PUBLIC_PATHS, AuthMiddleware


def _echo_claims(request: Request) -> JSONResponse:
    """Test endpoint that returns whatever claims were set on state."""
    claims = getattr(request.state, "claims", None)
    return JSONResponse({"claims": claims})


def _make_test_app() -> Starlette:
    app = Starlette(routes=[Route("/secret", _echo_claims), Route("/health", _echo_claims)])
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
# Protected path — missing / malformed Authorization header
# ---------------------------------------------------------------------------


def test_missing_authorization_header_returns_401(client: TestClient) -> None:
    response = client.get("/secret")
    assert response.status_code == 401


def test_wrong_auth_scheme_returns_401(client: TestClient) -> None:
    response = client.get("/secret", headers={"Authorization": "Basic dXNlcjpwYXNz"})
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
        response = client.get("/secret", headers={"Authorization": "Bearer bad.token.here"})
    assert response.status_code == 401


def test_invalid_token_body_has_error_code(client: TestClient) -> None:
    with patch("app.core.middleware.decode_jwt", new_callable=AsyncMock, return_value=None):
        response = client.get("/secret", headers={"Authorization": "Bearer bad.token.here"})
    assert response.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"


# ---------------------------------------------------------------------------
# Protected path — valid token
# ---------------------------------------------------------------------------


def test_valid_token_passes_through(client: TestClient) -> None:
    fake_claims = {"sub": "user-123", "role": "teacher", "email": "t@school.pk"}
    with patch("app.core.middleware.decode_jwt", new_callable=AsyncMock, return_value=fake_claims):
        with patch("app.core.middleware._account_status_block", new_callable=AsyncMock, return_value=None):
            response = client.get("/secret", headers={"Authorization": "Bearer valid.token.here"})
    assert response.status_code == 200


def test_valid_token_claims_set_on_request_state(client: TestClient) -> None:
    fake_claims = {"sub": "user-123", "role": "teacher"}
    with patch("app.core.middleware.decode_jwt", new_callable=AsyncMock, return_value=fake_claims):
        with patch("app.core.middleware._account_status_block", new_callable=AsyncMock, return_value=None):
            response = client.get("/secret", headers={"Authorization": "Bearer valid.token.here"})
    assert response.json()["claims"]["sub"] == "user-123"
    assert response.json()["claims"]["role"] == "teacher"


def test_suspended_user_returns_403(client: TestClient) -> None:
    fake_claims = {"sub": "user-123", "role": "teacher"}
    blocked = JSONResponse(
        status_code=403,
        content={"error": {"code": "ACCOUNT_SUSPENDED", "message": "Account suspended"}},
    )
    with patch("app.core.middleware.decode_jwt", new_callable=AsyncMock, return_value=fake_claims):
        with patch("app.core.middleware._account_status_block", new_callable=AsyncMock, return_value=blocked):
            response = client.get("/secret", headers={"Authorization": "Bearer valid.token.here"})
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ACCOUNT_SUSPENDED"
