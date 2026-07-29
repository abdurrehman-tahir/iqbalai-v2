"""ASGI middleware — AuthMiddleware validates JWT on every non-public request."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.config import get_settings
from app.core.cookies import ACCESS_COOKIE
from app.core.security import blacklist_id_for, decode_jwt, is_jti_blacklisted
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
        # Called when the access token is expired/missing — by definition can't
        # require a valid access token itself. Validates the iqbalai_refresh
        # cookie internally instead (T-244, ARCH §6.9).
        "/api/v1/auth/refresh",
        # Must work "with a dying session" (T-246, ARCH §6.8) — an expired or
        # already-invalid access cookie can't gate the one request whose job
        # is clearing that exact cookie. The route decodes the token itself
        # (best-effort) to blacklist its jti; a token that's already garbage
        # has nothing to blacklist, but cookies still get cleared either way.
        "/api/v1/auth/logout",
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
# reach: post-login (runs before the FE even knows tos_acceptance_required)
# and the accept/decline endpoints themselves (the only way out of the gate).
# `/auth/logout` doesn't need an entry here (T-246) — it's in PUBLIC_PATHS
# instead, which short-circuits dispatch before this check ever runs.
TOS_ALLOWED_PATHS: frozenset[str] = frozenset(
    {
        "/api/v1/auth/post-login",
        "/api/v1/users/me/accept-tos",
        "/api/v1/users/me/decline-tos",
    }
)


def _origin_allowed(request: Request) -> bool:
    """CSRF defense-in-depth for mutating methods (T-244, ARCH §6.17).

    SameSite=Lax on the session cookies is the primary defense (a cross-site
    POST/fetch never carries them at all in modern browsers); this Origin/
    Referer check is the second layer the threat table calls for. Enforced
    unconditionally for every mutating request — including PUBLIC_PATHS ones
    like /auth/refresh or /independent/signup, since Origin validity doesn't
    depend on whether the endpoint requires a token.

    Only enforced when the browser actually sent Origin or Referer: non-browser
    API clients (tests, curl, tooling) that send neither are unaffected — real
    browsers always send at least one on a state-changing request.
    """
    allowed_origins = get_settings().cors_allowed_origins

    origin = request.headers.get("origin")
    if origin is not None:
        return origin in allowed_origins

    referer = request.headers.get("referer")
    if referer is not None:
        return any(referer.startswith(o) for o in allowed_origins)

    return True


def _origin_rejected_response() -> JSONResponse:
    return JSONResponse(
        status_code=403,
        content={
            "error": {
                "code": "ORIGIN_NOT_ALLOWED",
                "message": "Cross-origin request rejected",
            }
        },
    )


def _extract_access_token(request: Request) -> str | None:
    """Read the access token from the `iqbalai_access` cookie (ARCH §6.6).

    T-244 briefly kept an `Authorization: Bearer` fallback for tooling; T-245
    (the frontend cutover to cookies) removes it — the cookie is the only
    credential path now, matching §6.17 ("never JS-accessible" — a header the
    browser client sets would mean the token was readable by JS in the first
    place, defeating the point of HttpOnly cookies).
    """
    return request.cookies.get(ACCESS_COOKIE) or None


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

        if request.method in _STATE_CHANGING_METHODS and not _origin_allowed(request):
            return _origin_rejected_response()

        if request.url.path in PUBLIC_PATHS:
            return await call_next(request)

        token = _extract_access_token(request)
        if token is None:
            return JSONResponse(
                status_code=401,
                content={
                    "error": {
                        "code": "AUTHENTICATION_REQUIRED",
                        "message": "Authentication required",
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

        # Logout blacklists the jti until natural expiry (T-246, ARCH §6.8) —
        # a signature-valid, unexpired token can still be dead if its owner
        # already logged out with it.
        if await is_jti_blacklisted(blacklist_id_for(token, claims)):
            return JSONResponse(
                status_code=401,
                content={
                    "error": {
                        "code": "AUTHENTICATION_REQUIRED",
                        "message": "Session has been logged out",
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
