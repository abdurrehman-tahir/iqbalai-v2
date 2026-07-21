"""Auth endpoints — server-owned OIDC redirect flow (ARCH §6.4)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.dependencies import get_current_user, get_db
from app.core.responses import SuccessEnvelope, success
from app.core.security import blacklist_jti, decode_jwt
from app.features.auth.oidc import (
    complete_login,
    revoke_refresh_token,
    rotate_refresh_token,
    save_refresh_token,
    start_login,
)
from app.features.auth.schemas import PostLoginResponse
from app.features.auth.service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])
_ACCESS_COOKIE = "iqbalai_access"
_REFRESH_COOKIE = "iqbalai_refresh"
_TRANSIENT_COOKIE = "iqbalai_oidc_state"
_ACCESS_MAX_AGE = 24 * 60 * 60
_REFRESH_MAX_AGE = 30 * 24 * 60 * 60


def _set_session_cookies(
    response: RedirectResponse | JSONResponse, access: str, refresh: str
) -> None:
    """Set the locked §6.17 cookie attributes in one place."""
    response.set_cookie(
        _ACCESS_COOKIE,
        access,
        max_age=_ACCESS_MAX_AGE,
        path="/",
        secure=True,
        httponly=True,
        samesite="lax",
    )
    response.set_cookie(
        _REFRESH_COOKIE,
        refresh,
        max_age=_REFRESH_MAX_AGE,
        path="/",
        secure=True,
        httponly=True,
        samesite="lax",
    )


def _post_login_path(role: str) -> str:
    paths = {
        "platform_admin": "/admin",
        "district_admin": "/admin/district/schools",
        "school_admin": "/school/admin",
        "coordinator": "/coordinator",
        "teacher": "/teacher",
        "student": "/student",
        "parent": "/parent",
        "independent_teacher": "/independent/teacher",
        "independent_student": "/independent/student",
    }
    return paths.get(role, "/")


@router.get("/login", response_model=None, operation_id="oidc_login", include_in_schema=True)
async def login(next: str | None = Query(default=None)) -> RedirectResponse:
    """Create server-side state/nonce/PKCE and redirect to Authentik."""
    transient_id, redirect_url = await start_login(next)
    response = RedirectResponse(redirect_url, status_code=status.HTTP_302_FOUND)
    response.set_cookie(
        _TRANSIENT_COOKIE,
        transient_id,
        max_age=600,
        path="/api/v1/auth",
        secure=True,
        httponly=True,
        samesite="lax",
    )
    return response


@router.get("/callback", response_model=None, operation_id="oidc_callback", include_in_schema=True)
async def callback(
    request: Request,
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    """Validate callback state/nonce, provision the user, then create cookie session."""
    try:
        tokens, next_path = await complete_login(
            request.cookies.get(_TRANSIENT_COOKIE), state, code
        )
        claims = await decode_jwt(tokens.access_token)
        if claims is None:
            raise ValueError("Invalid access token received from identity provider")
        login_result = await AuthService(db).post_login(claims)
    except (ValueError, HTTPException):
        return RedirectResponse(
            f"{get_settings().APP_URL.rstrip('/')}/login?error=authentication_failed",
            status_code=status.HTTP_302_FOUND,
        )

    refresh_reference = await save_refresh_token(tokens.refresh_token)
    destination = (
        "/auth/callback?tos=required"
        if bool(login_result["tos_acceptance_required"])
        else next_path
        if next_path != "/"
        else _post_login_path(str(login_result["role"]))
    )
    response = RedirectResponse(
        f"{get_settings().APP_URL.rstrip('/')}{destination}",
        status_code=status.HTTP_302_FOUND,
    )
    _set_session_cookies(response, tokens.access_token, refresh_reference)
    response.delete_cookie(_TRANSIENT_COOKIE, path="/api/v1/auth")
    return response


@router.post(
    "/refresh",
    response_model=dict[str, dict[str, bool]],
    operation_id="refresh_cookie_session",
    include_in_schema=True,
)
async def refresh(request: Request) -> JSONResponse:
    """Rotate the opaque refresh reference and replace the access cookie."""
    try:
        access, reference = await rotate_refresh_token(request.cookies.get(_REFRESH_COOKIE, ""))
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Session refresh failed"
        ) from None
    response = JSONResponse({"data": {"refreshed": True}})
    _set_session_cookies(response, access, reference)
    return response


@router.get(
    "/me",
    response_model=SuccessEnvelope[PostLoginResponse],
    operation_id="get_authenticated_user",
)
async def me(
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Return cookie-session user state for the frontend shell and ToS modal."""
    result = await AuthService(db).post_login(claims)
    return success(PostLoginResponse.model_validate(result).model_dump())


@router.post(
    "/logout",
    response_model=dict[str, dict[str, bool]],
    operation_id="logout_cookie_session",
)
async def logout(request: Request) -> JSONResponse:
    """Revoke refresh state and remove browser cookies."""
    access_token = request.cookies.get(_ACCESS_COOKIE)
    if access_token:
        claims = await decode_jwt(access_token)
        if claims is not None:
            await blacklist_jti(claims)
    await revoke_refresh_token(request.cookies.get(_REFRESH_COOKIE))
    response = JSONResponse({"data": {"logged_out": True}})
    response.delete_cookie(_ACCESS_COOKIE, path="/")
    response.delete_cookie(_REFRESH_COOKIE, path="/")
    return response


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
