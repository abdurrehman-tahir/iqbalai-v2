"""ASGI middleware — AuthMiddleware validates JWT on every non-public request."""

from __future__ import annotations

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.security import decode_jwt

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
        "/metrics",
    }
)


class AuthMiddleware(BaseHTTPMiddleware):
    """Validate JWT bearer token on every request except PUBLIC_PATHS.

    On success: sets request.state.claims (dict of JWT claims).
    On failure: returns 401 JSON error envelope immediately.
    """

    async def dispatch(self, request: Request, call_next: object) -> Response:
        if request.url.path in PUBLIC_PATHS:
            return await call_next(request)  # type: ignore[operator]

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
        claims = decode_jwt(token)
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

        request.state.claims = claims
        return await call_next(request)  # type: ignore[operator]
