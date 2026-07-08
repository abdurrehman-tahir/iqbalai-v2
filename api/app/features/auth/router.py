"""Auth endpoints — T-016 (post-login) + M-07b T-240 (BFF login/session)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.core.dependencies import get_current_user, get_db
from app.core.exceptions import AuthenticationError
from app.core.responses import SuccessEnvelope, success
from app.core.tenant import get_tenant_type
from app.features.auth.schemas import (
    ForgotPasswordRequest,
    LoginRequest,
    LoginResponse,
    PostLoginResponse,
    ResetPasswordRequest,
)
from app.features.auth.service import AuthService
from app.infrastructure.authentik.auth import TokenPair, get_auth_backend

router = APIRouter(prefix="/auth", tags=["auth"])

ACCESS_COOKIE = "iqbalai_access"
REFRESH_COOKIE = "iqbalai_refresh"


def _set_session_cookies(response: Response, pair: TokenPair, settings: Settings) -> None:
    """Set the HttpOnly access + refresh cookies per ARCH §6.4."""
    domain = settings.COOKIE_DOMAIN or None
    response.set_cookie(
        ACCESS_COOKIE,
        pair.access_token,
        max_age=settings.ACCESS_COOKIE_MAX_AGE,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="lax",
        path="/",
        domain=domain,
    )
    response.set_cookie(
        REFRESH_COOKIE,
        pair.refresh_token,
        max_age=settings.REFRESH_COOKIE_MAX_AGE,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="lax",
        path="/",
        domain=domain,
    )


def _clear_session_cookies(response: Response, settings: Settings) -> None:
    domain = settings.COOKIE_DOMAIN or None
    response.delete_cookie(ACCESS_COOKIE, path="/", domain=domain)
    response.delete_cookie(REFRESH_COOKIE, path="/", domain=domain)


@router.post(
    "/login",
    response_model=SuccessEnvelope[LoginResponse],
    operation_id="login",
    summary="BFF login — validate credentials server-side, set session cookies",
    description=(
        "Validates email + password against Authentik server-side (never in the "
        "browser), sets HttpOnly session cookies, and runs post-login (User upsert + "
        "ToS status) so the frontend can redirect by role. M-07b / ARCH §6.4 (A-003)."
    ),
)
async def login(
    payload: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    backend = get_auth_backend()
    pair = await backend.authenticate(payload.email, payload.password)

    claims = dict(pair.claims)
    claims["tenant_type"] = get_tenant_type(claims)

    svc = AuthService(db)
    result = await svc.post_login(claims)

    _set_session_cookies(response, pair, settings)
    return success(LoginResponse.model_validate(result).model_dump())


@router.post(
    "/refresh",
    response_model=SuccessEnvelope[None],
    operation_id="refresh_session",
    summary="Rotate the access cookie using the refresh cookie",
)
async def refresh_session(
    request: Request,
    response: Response,
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    refresh_token = request.cookies.get(REFRESH_COOKIE)
    if not refresh_token:
        raise AuthenticationError("No refresh session")
    pair = await get_auth_backend().refresh(refresh_token)
    _set_session_cookies(response, pair, settings)
    return success(None)


@router.post(
    "/logout",
    response_model=SuccessEnvelope[None],
    operation_id="logout",
    summary="Revoke the refresh token and clear session cookies",
)
async def logout(
    request: Request,
    response: Response,
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    refresh_token = request.cookies.get(REFRESH_COOKIE)
    if refresh_token:
        await get_auth_backend().revoke(refresh_token)
    _clear_session_cookies(response, settings)
    return success(None)


@router.post(
    "/forgot-password",
    response_model=SuccessEnvelope[None],
    operation_id="forgot_password",
    summary="Trigger a password-reset email (always 200 — no account enumeration)",
)
async def forgot_password(payload: ForgotPasswordRequest) -> dict[str, Any]:
    # Always returns 200 regardless of whether the email exists (ARCH §6.17).
    await get_auth_backend().request_password_reset(payload.email)
    return success(None, "If an account exists, we sent password-reset instructions")


@router.post(
    "/reset-password",
    response_model=SuccessEnvelope[None],
    operation_id="reset_password",
    summary="Complete a password reset with the token from the recovery email",
)
async def reset_password(payload: ResetPasswordRequest) -> dict[str, Any]:
    await get_auth_backend().confirm_password_reset(payload.token, payload.new_password)
    return success(None, "Password updated — sign in with your new password")


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
