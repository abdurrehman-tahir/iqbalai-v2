"""ASGI middleware — AuthMiddleware validates JWT on every non-public request."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.security import decode_jwt
from app.db.session import async_session_factory
from app.features.users.models import UserAccountStatus
from app.features.users.repository import UserRepository

logger = structlog.get_logger(__name__)

# Paths that skip JWT validation entirely
PUBLIC_PATHS: frozenset[str] = frozenset(
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
        "/api/v1/auth/accept-invite",
        "/metrics",
    }
)


async def _account_status_block(authentik_id: str) -> JSONResponse | None:
    """Return a 403 response when the user account is not active."""
    if not authentik_id:
        return None

    async with async_session_factory() as session:
        repo = UserRepository(session)
        user = await repo.get_by_authentik_id_any(authentik_id)

    if user is None:
        return None

    if user.deleted_at is not None or user.status == UserAccountStatus.DEACTIVATED:
        return JSONResponse(
            status_code=403,
            content={
                "error": {
                    "code": "ACCOUNT_DEACTIVATED",
                    "message": "Account deactivated — contact your administrator",
                }
            },
        )

    if user.status == UserAccountStatus.SUSPENDED:
        return JSONResponse(
            status_code=403,
            content={
                "error": {
                    "code": "ACCOUNT_SUSPENDED",
                    "message": "Account suspended — contact your administrator",
                }
            },
        )

    return None


class AuthMiddleware(BaseHTTPMiddleware):
    """Validate JWT bearer token on every request except PUBLIC_PATHS.

    On success: sets request.state.claims (dict of JWT claims).
    On failure: returns 401 JSON error envelope immediately.
    """

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        # Browsers send OPTIONS preflight before cross-origin POST with Authorization.
        if request.method == "OPTIONS":
            return await call_next(request)

        if request.url.path in PUBLIC_PATHS:
            return await call_next(request)

        authorization = request.headers.get("Authorization", "")
        if not authorization.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={
                    "error": {
                        "code": "AUTHENTICATION_REQUIRED",
                        "message": "Bearer token required",
                    }
                },
            )

        token = authorization.removeprefix("Bearer ")
        claims = await decode_jwt(token)
        if claims is None:
            return JSONResponse(
                status_code=401,
                content={
                    "error": {
                        "code": "AUTHENTICATION_REQUIRED",
                        "message": "Invalid or expired token",
                    }
                },
            )

        blocked = await _account_status_block(str(claims.get("sub", "")))
        if blocked is not None:
            return blocked

        request.state.claims = claims
        return await call_next(request)
