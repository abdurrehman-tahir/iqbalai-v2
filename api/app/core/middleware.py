"""ASGI middleware — AuthMiddleware validates JWT on every non-public request."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.security import decode_jwt
from app.core.tenant import get_tenant_type
from app.db.session import async_session_factory
from app.features.independent_users.models import IndependentUser, IndependentUserAccountStatus
from app.features.independent_users.repository import IndependentUserRepository
from app.features.users.models import User, UserAccountStatus
from app.features.users.repository import UserRepository
from app.features.users.service import _ROLE_LOGIN_PRIORITY

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
        "/api/v1/independent/signup",
        "/metrics",
    }
)


def _enrich_claims_from_user(claims: dict[str, object], user: User | IndependentUser) -> dict[str, object]:
    """Override JWT role/scope with the app database — Authentik tokens lack app roles."""
    enriched = dict(claims)
    enriched["role"] = user.role.value
    enriched["user_id"] = user.id
    if isinstance(user, User):
        enriched["tenant_type"] = "school"
        if user.district_id:
            enriched["district_id"] = user.district_id
        if user.school_id:
            enriched["school_id"] = user.school_id
    else:
        enriched["tenant_type"] = "independent"
        enriched["school_id"] = None
        enriched["district_id"] = None
        enriched["language_preference"] = user.language_preference
    return enriched


async def _resolve_active_user(claims: dict[str, object]) -> User | IndependentUser | None:
    """Look up the active app user for JWT sub (fallback: email for invite ID mismatch)."""
    authentik_id = str(claims.get("sub", ""))
    if not authentik_id:
        return None

    tenant_type = get_tenant_type(claims)

    async with async_session_factory() as session:
        if tenant_type == "independent":
            repo = IndependentUserRepository(session)
            user = await repo.get_by_authentik_id(authentik_id)
            if user is not None:
                return user
            email = str(claims.get("email", "")).strip().lower()
            if email:
                return await repo.get_by_email(email)
            return None

        repo = UserRepository(session)
        user = await repo.get_by_authentik_id(authentik_id)
        if user is not None:
            return user

        email = str(claims.get("email", "")).strip().lower()
        if not email:
            return None

        matches = await repo.list_by_email(email)
        if not matches:
            return None

        return max(matches, key=lambda row: _ROLE_LOGIN_PRIORITY.get(row.role, 0))


def _account_status_block(user: User | IndependentUser) -> JSONResponse | None:
    """Return a 403 response when the user account is not active."""
    if user.deleted_at is not None:
        return JSONResponse(
            status_code=403,
            content={
                "error": {
                    "code": "ACCOUNT_DEACTIVATED",
                    "message": "Account deactivated — contact your administrator",
                }
            },
        )

    if isinstance(user, User):
        if user.status == UserAccountStatus.DEACTIVATED:
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
    elif user.status == IndependentUserAccountStatus.DEACTIVATED:
        return JSONResponse(
            status_code=403,
            content={
                "error": {
                    "code": "ACCOUNT_DEACTIVATED",
                    "message": "Account deactivated — contact support",
                }
            },
        )
    elif user.status == IndependentUserAccountStatus.SUSPENDED:
        return JSONResponse(
            status_code=403,
            content={
                "error": {
                    "code": "ACCOUNT_SUSPENDED",
                    "message": "Account suspended — contact support",
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

        claims["tenant_type"] = get_tenant_type(claims)

        user = await _resolve_active_user(claims)
        if user is not None:
            blocked = _account_status_block(user)
            if blocked is not None:
                return blocked
            claims = _enrich_claims_from_user(claims, user)

        request.state.claims = claims
        return await call_next(request)
