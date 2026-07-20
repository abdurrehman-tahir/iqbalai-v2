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
from app.features.tos.service import TosService
from app.features.users.models import User, UserAccountStatus, UserRole
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
        "/api/v1/parents/signup",
        "/metrics",
    }
)

# State-changing methods the ToS gate applies to (T-242, audit C4). GET stays
# readable so the FE can render the ToS modal + content before the user acts.
_STATE_CHANGING_METHODS: frozenset[str] = frozenset({"POST", "PUT", "PATCH", "DELETE"})

# Authenticated paths a caller with an unaccepted ToS must still be able to
# reach: post-login (runs before the FE even knows tos_acceptance_required),
# the accept/decline endpoints themselves (the only way out of the gate), and
# logout (a user must always be able to sign out). `/auth/logout` doesn't
# exist yet (T-246) — listed proactively so that ticket doesn't need to
# re-touch this set.
TOS_ALLOWED_PATHS: frozenset[str] = frozenset(
    {
        "/api/v1/auth/post-login",
        "/api/v1/auth/logout",
        "/api/v1/users/me/accept-tos",
        "/api/v1/users/me/decline-tos",
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


async def _tos_acceptance_required(user: User | IndependentUser) -> bool:
    """True if `user` has not accepted the current ToS version.

    ``tos_acceptance_required`` is not a persisted column — it's computed
    per-request the same way ``AuthService.post_login`` and
    ``TosService.require_tos_accepted`` already compute it.
    """
    async with async_session_factory() as session:
        return not await TosService(session).check_user_has_accepted_current(user.id)


def _tos_acceptance_block() -> JSONResponse:
    """Return the 403 a state-changing request gets when ToS isn't accepted.

    Today the modal dismisses without consequence — the token stays fully
    capable. This makes the gate enforcement, not decoration (T-242, audit C4).
    """
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
            if blocked is not None and not _allow_suspended_parent_post_login(request, user):
                return blocked

            if (
                request.method in _STATE_CHANGING_METHODS
                and request.url.path not in TOS_ALLOWED_PATHS
                and await _tos_acceptance_required(user)
            ):
                return _tos_acceptance_block()

            claims = _enrich_claims_from_user(claims, user)

        request.state.claims = claims
        return await call_next(request)
