"""Auth endpoints — T-016 (post-login handler) + T-244 (server-side OIDC, ARCH §6.4)."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.cookies import (
    REFRESH_COOKIE,
    set_access_cookie,
    set_refresh_cookie,
    set_session_cookies,
)
from app.core.dependencies import get_current_user, get_db
from app.core.exceptions import AuthenticationError
from app.core.responses import SuccessEnvelope, success
from app.core.security import decode_jwt
from app.core.tenant import get_tenant_type
from app.features.auth.oidc_client import (
    OAuthError,
    build_authorize_url,
    exchange_code_for_token,
    exchange_refresh_token,
)
from app.features.auth.oidc_session import (
    OIDC_SESSION_COOKIE,
    consume_oidc_session,
    create_oidc_session,
    safe_next_path,
)
from app.features.auth.refresh_session import resolve_and_rotate, store_refresh_token
from app.features.auth.schemas import MeResponse, PostLoginResponse
from app.features.auth.service import AuthService, get_post_login_path

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

# Transient OIDC-session cookie: scoped narrowly to the auth prefix (not "/"),
# 10 minutes — just long enough to complete an interactive Authentik login.
_OIDC_SESSION_MAX_AGE = 600
_OIDC_SESSION_COOKIE_PATH = "/api/v1/auth"


def _callback_url(request: Request) -> str:
    """The API's own callback URL, as the browser actually reached this API —
    must exactly match what was sent to Authentik in the authorize request
    (OAuth2 requires the same redirect_uri on both legs)."""
    return str(request.base_url).rstrip("/") + "/api/v1/auth/callback"


@router.post(
    "/post-login",
    response_model=SuccessEnvelope[PostLoginResponse],
    operation_id="post_login",
    summary="Post-OIDC-login handler",
    description=(
        "Called by the frontend after every successful Authentik OIDC callback. "
        "Creates a User row on first login. Returns ToS acceptance status so the "
        "frontend can show the acceptance modal if needed."
    ),
)
async def post_login(
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = AuthService(db)
    result = await svc.post_login(claims)
    return success(PostLoginResponse.model_validate(result).model_dump())


@router.get(
    "/me",
    response_model=SuccessEnvelope[MeResponse],
    operation_id="auth_me",
    summary="Current user's display state (T-245)",
    description=(
        "Tokens are HttpOnly cookies now — the frontend can't decode them for "
        "display state. Returns the same claims AuthMiddleware already "
        "enriched from the DB on every authenticated request."
    ),
)
async def me(claims: dict[str, object] = Depends(get_current_user)) -> dict[str, Any]:
    district_id = claims.get("district_id")
    school_id = claims.get("school_id")
    return success(
        MeResponse(
            user_id=str(claims.get("user_id", "")),
            email=str(claims.get("email", "")),
            role=str(claims.get("role", "")),
            tenant_type=str(claims.get("tenant_type", "school")),
            district_id=district_id if isinstance(district_id, str) else None,
            school_id=school_id if isinstance(school_id, str) else None,
        ).model_dump()
    )


@router.get(
    "/login",
    response_model=None,
    operation_id="auth_login",
    summary="Start the OIDC login redirect (ARCH §6.4 step 1-2)",
    description=(
        "Generates state (CSRF), nonce, and a PKCE S256 challenge; stores them "
        "server-side in Redis keyed by a transient cookie; redirects the browser "
        "to Authentik's authorize endpoint. No response body — always a 302. "
        "`prompt_login`/`login_hint` are for post-invite and post-signup flows "
        "that need to force a fresh login pre-filled with the verified email, "
        "rather than silently reusing an unrelated existing SSO session."
    ),
    responses={302: {"description": "Redirect to Authentik's authorize endpoint"}},
)
async def login(
    request: Request,
    next: str | None = None,
    prompt_login: bool = False,
    login_hint: str | None = None,
) -> RedirectResponse:
    # "" (not "/") means "nothing requested" — callback must be able to tell
    # that apart from an explicit `next=/`, so it can fall back to the role
    # dashboard instead of always landing on the site root.
    next_path = safe_next_path(next, default="")
    session_id, session = await create_oidc_session(next_path)

    authorize_url = build_authorize_url(
        redirect_uri=_callback_url(request),
        state=session.state,
        nonce=session.nonce,
        code_verifier=session.code_verifier,
        prompt_login=prompt_login,
        login_hint=login_hint,
    )

    response = RedirectResponse(url=authorize_url, status_code=302)
    response.set_cookie(
        key=OIDC_SESSION_COOKIE,
        value=session_id,
        max_age=_OIDC_SESSION_MAX_AGE,
        path=_OIDC_SESSION_COOKIE_PATH,
        secure=get_settings().COOKIE_SECURE,
        httponly=True,
        samesite="lax",
    )
    return response


@router.get(
    "/callback",
    response_model=None,
    operation_id="auth_callback",
    summary="OIDC callback — server-side code+PKCE exchange (ARCH §6.4 steps 7-11)",
    description=(
        "Validates state, exchanges the code + PKCE verifier with Authentik "
        "server-side, validates the id_token nonce, provisions/looks up the "
        "user, sets the iqbalai_access/iqbalai_refresh cookies, and redirects "
        "to the caller's dashboard. Any failure redirects to a clean error page "
        "— never a hang, never a 500 for an untrusted callback."
    ),
    responses={302: {"description": "Redirect to the dashboard, or to a login error page"}},
)
async def callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    settings = get_settings()
    session_id = request.cookies.get(OIDC_SESSION_COOKIE)

    def _reject(reason: str) -> RedirectResponse:
        logger.warning("oidc_callback_rejected", reason=reason)
        resp = RedirectResponse(url=f"{settings.APP_URL}/login?error=auth_failed", status_code=302)
        resp.delete_cookie(OIDC_SESSION_COOKIE, path=_OIDC_SESSION_COOKIE_PATH)
        return resp

    if error:
        return _reject(f"authentik_error:{error}")
    if not code or not state or not session_id:
        return _reject("missing_code_state_or_session")

    oidc_session = await consume_oidc_session(session_id)
    if oidc_session is None:
        return _reject("session_expired_or_already_used")
    if state != oidc_session.state:
        return _reject("state_mismatch")

    try:
        token = await exchange_code_for_token(
            code=code,
            code_verifier=oidc_session.code_verifier,
            redirect_uri=_callback_url(request),
        )
    except OAuthError as exc:
        return _reject(f"token_exchange_failed:{exc.error}")

    id_token = token.get("id_token")
    access_token = token.get("access_token")
    refresh_token = token.get("refresh_token")
    if not isinstance(id_token, str) or not isinstance(access_token, str):
        return _reject("missing_tokens_in_response")

    claims = await decode_jwt(id_token)
    if claims is None:
        return _reject("id_token_invalid")
    if claims.get("nonce") != oidc_session.nonce:
        return _reject("nonce_mismatch")

    claims["tenant_type"] = get_tenant_type(claims)
    result = await AuthService(db).post_login(claims)

    role = str(result["role"])
    tos_required = bool(result["tos_acceptance_required"])
    target_path = (
        "/auth/callback?tos_required=1"
        if tos_required
        else safe_next_path(oidc_session.next_path or None, default=get_post_login_path(role))
    )

    response = RedirectResponse(url=f"{settings.APP_URL}{target_path}", status_code=302)
    response.delete_cookie(OIDC_SESSION_COOKIE, path=_OIDC_SESSION_COOKIE_PATH)

    if isinstance(refresh_token, str) and refresh_token:
        refresh_ref = await store_refresh_token(refresh_token)
        set_session_cookies(response, access_token=access_token, refresh_ref=refresh_ref)
    else:
        set_access_cookie(response, access_token=access_token)

    logger.info(
        "oidc_login_succeeded",
        user_id=result.get("user_id"),
        role=role,
        is_first_login=result.get("is_first_login"),
        tos_acceptance_required=tos_required,
    )
    return response


@router.post(
    "/refresh",
    response_model=None,
    operation_id="auth_refresh",
    summary="Refresh the access token from the iqbalai_refresh cookie (ARCH §6.9)",
    description=(
        "Reads the opaque iqbalai_refresh reference, resolves it to the real "
        "Authentik refresh token server-side, exchanges it for a new access "
        "token, and rotates the reference (single-use). No request body."
    ),
    status_code=204,
)
async def refresh(request: Request, response: Response) -> None:
    opaque_ref = request.cookies.get(REFRESH_COOKIE)
    if not opaque_ref:
        raise AuthenticationError("No refresh session")

    real_refresh_token = await resolve_and_rotate(opaque_ref)
    if real_refresh_token is None:
        raise AuthenticationError("Refresh session expired or already used")

    try:
        token = await exchange_refresh_token(real_refresh_token)
    except OAuthError as exc:
        logger.warning("refresh_token_rejected", reason=exc.error)
        raise AuthenticationError("Refresh token rejected") from exc

    access_token = token.get("access_token")
    new_refresh_token = token.get("refresh_token")
    if not isinstance(access_token, str):
        raise AuthenticationError("Refresh response missing access_token")

    set_access_cookie(response, access_token=access_token)
    if isinstance(new_refresh_token, str) and new_refresh_token:
        new_ref = await store_refresh_token(new_refresh_token)
        set_refresh_cookie(response, refresh_ref=new_ref)
    return None
