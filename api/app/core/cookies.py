"""HttpOnly session cookie constants + helpers (T-244, ARCH §6.4/§6.17).

Two cookies carry the session: ``iqbalai_access`` (JWT, 24h) and
``iqbalai_refresh`` (opaque reference, 30d — see ``refresh_session.py``).
Both HttpOnly + Secure + SameSite=Lax + Path=/. Never JS-readable, never sent
cross-site except on a top-level GET navigation.
"""

from __future__ import annotations

from starlette.responses import Response

from app.config import get_settings

ACCESS_COOKIE = "iqbalai_access"
REFRESH_COOKIE = "iqbalai_refresh"

ACCESS_MAX_AGE = 24 * 60 * 60  # 24h
REFRESH_MAX_AGE = 30 * 24 * 60 * 60  # 30d


def set_access_cookie(response: Response, *, access_token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        key=ACCESS_COOKIE,
        value=access_token,
        max_age=ACCESS_MAX_AGE,
        path="/",
        secure=settings.COOKIE_SECURE,
        httponly=True,
        samesite="lax",
    )


def set_refresh_cookie(response: Response, *, refresh_ref: str) -> None:
    settings = get_settings()
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=refresh_ref,
        max_age=REFRESH_MAX_AGE,
        path="/",
        secure=settings.COOKIE_SECURE,
        httponly=True,
        samesite="lax",
    )


def set_session_cookies(response: Response, *, access_token: str, refresh_ref: str) -> None:
    set_access_cookie(response, access_token=access_token)
    set_refresh_cookie(response, refresh_ref=refresh_ref)


def clear_session_cookies(response: Response) -> None:
    """Clear both session cookies (also used by T-246 logout)."""
    response.delete_cookie(ACCESS_COOKIE, path="/")
    response.delete_cookie(REFRESH_COOKIE, path="/")
