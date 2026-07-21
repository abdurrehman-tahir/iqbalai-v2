"""ASGI middleware — AuthMiddleware validates JWT on every non-public request."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.config import get_settings
from app.core.security import decode_jwt, is_jti_blacklisted
from app.core.tenant import get_tenant_type
from app.db.session import async_session_factory
from app.features.independent_users.models import IndependentUser, IndependentUserAccountStatus
from app.features.independent_users.repository import IndependentUserRepository
from app.features.users.models import User, UserAccountStatus, UserRole
from app.features.users.repository import UserRepository
from app.features.users.service import _ROLE_LOGIN_PRIORITY

logger = structlog.get_logger(__name__)
_STATE_CHANGING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
_TOS_COMPLETION_PATHS = frozenset(
    {
        "/api/v1/auth/post-login",
        "/api/v1/auth/logout",
        "/api/v1/users/me/accept-tos",
        "/api/v1/users/me/decline-tos",
    }
)

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
        "/api/v1/auth/refresh",
        "/api/v1/auth/logout",
        "/api/v1/auth/accept-invite",
        "/api/v1/independent/signup",
        "/api/v1/parents/signup",
        "/metrics",
    }
)


def _enrich_claims_from_user(
    claims: dict[str, object], user: User | IndependentUser
) -> dict[str, object]:
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
            indep_repo = IndependentUserRepository(session)
            user = await indep_repo.get_by_authentik_id(authentik_id)
            if user is not None:
                return user
            email = str(claims.get("email", "")).strip().lower()
            if email:
                return await indep_repo.get_by_email(email)
            return None

        user_repo = UserRepository(session)
        school_user = await user_repo.get_by_authentik_id(authentik_id)
        if school_user is not None:
            return school_user

        email = str(claims.get("email", "")).strip().lower()
        if not email:
            return None

        matches = await user_repo.list_by_email(email)
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


async def _tos_required_block(
    request: Request, user: User | IndependentUser
) -> JSONResponse | None:
    """Enforce ToS acceptance before a user can mutate application state."""
    if request.method not in _STATE_CHANGING_METHODS or request.url.path in _TOS_COMPLETION_PATHS:
        return None

    from app.features.tos.service import TosService

    async with async_session_factory() as session:
        accepted = await TosService(session).check_user_has_accepted_current(user.id)
    if accepted:
        return None
    return JSONResponse(
        status_code=403,
        content={
            "error": {
                "code": "TOS_ACCEPTANCE_REQUIRED",
                "message": "Terms of Service acceptance required",
            }
        },
    )


def _allow_suspended_parent_post_login(request: Request, user: User | IndependentUser) -> bool:
    """Let auto-suspended unlinked parents reach post-login so auth can resume them."""
    return (
        request.url.path == "/api/v1/auth/post-login"
        and isinstance(user, User)
        and user.role == UserRole.PARENT
        and user.status == UserAccountStatus.SUSPENDED
    )


def _same_origin_mutation(request: Request) -> bool:
    """Apply the §6 CSRF Origin/Referer defense to cookie-authenticated writes."""
    if request.method not in _STATE_CHANGING_METHODS:
        return True
    expected = get_settings().APP_URL.rstrip("/")
    origin = request.headers.get("origin")
    if origin:
        return origin.rstrip("/") == expected
    referer = request.headers.get("referer")
    return bool(referer and referer.startswith(f"{expected}/"))


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

        token = request.cookies.get("iqbalai_access")
        authorization = request.headers.get("Authorization", "")
        # Temporary tooling compatibility during T-244. T-245 removes this
        # fallback once every browser/E2E helper uses the cookie session.
        if token is None and authorization.startswith("Bearer "):
            token = authorization.removeprefix("Bearer ")
        if token is None:
            return JSONResponse(
                status_code=401,
                content={
                    "error": {
                        "code": "AUTHENTICATION_REQUIRED",
                        "message": "Authentication cookie required",
                    }
                },
            )

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

        if await is_jti_blacklisted(claims):
            return JSONResponse(
                status_code=401,
                content={
                    "error": {
                        "code": "AUTHENTICATION_REQUIRED",
                        "message": "Session has been revoked",
                    }
                },
            )

        claims["tenant_type"] = get_tenant_type(claims)

        user = await _resolve_active_user(claims)
        if user is not None:
            blocked = _account_status_block(user)
            if blocked is not None and not _allow_suspended_parent_post_login(request, user):
                return blocked
            claims = _enrich_claims_from_user(claims, user)
            tos_blocked = await _tos_required_block(request, user)
            if tos_blocked is not None:
                return tos_blocked
        if not _same_origin_mutation(request):
            return JSONResponse(
                status_code=403,
                content={
                    "error": {
                        "code": "CSRF_ORIGIN_INVALID",
                        "message": "Cross-origin state-changing request rejected",
                    }
                },
            )

        request.state.claims = claims
        return await call_next(request)
