"""Server-side OIDC code+PKCE exchange with Authentik (T-244, ARCH §6.4 steps 2, 8-9).

authlib is the locked library for this (STACK_LOCK "Auth in FastAPI"). State,
nonce, and PKCE storage are handled by ``oidc_session.py`` (Redis) — this
module only builds the authorize redirect URL and performs the token exchange.
"""

from __future__ import annotations

from urllib.parse import urlencode

from authlib.integrations.base_client.errors import OAuthError
from authlib.integrations.httpx_client import AsyncOAuth2Client
from authlib.oauth2.rfc7636 import create_s256_code_challenge

from app.config import get_settings

__all__ = [
    "OAuthError",
    "build_authorize_url",
    "exchange_code_for_token",
    "exchange_refresh_token",
]


def build_authorize_url(*, redirect_uri: str, state: str, nonce: str, code_verifier: str) -> str:
    """Build the Authentik authorize redirect (ARCH §6.4 step 2)."""
    settings = get_settings()
    params = {
        "response_type": "code",
        "client_id": settings.OIDC_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "scope": "openid profile email",
        "state": state,
        "nonce": nonce,
        "code_challenge": create_s256_code_challenge(code_verifier),
        "code_challenge_method": "S256",
    }
    return f"{settings.OIDC_AUTHORIZE_URL}?{urlencode(params)}"


async def exchange_code_for_token(
    *, code: str, code_verifier: str, redirect_uri: str
) -> dict[str, object]:
    """Exchange the authorization code + PKCE verifier for tokens (ARCH §6.4 step 8).

    Raises ``authlib.integrations.base_client.errors.OAuthError`` on any
    OAuth2-level failure (invalid_grant, invalid_client, etc.) — callers map
    that to a clean rejection, never a hang or a 500.
    """
    settings = get_settings()
    client = AsyncOAuth2Client(
        client_id=settings.OIDC_CLIENT_ID,
        client_secret=settings.OIDC_CLIENT_SECRET or None,
        redirect_uri=redirect_uri,
    )
    async with client:
        token: dict[str, object] = await client.fetch_token(
            url=settings.OIDC_TOKEN_URL,
            grant_type="authorization_code",
            code=code,
            code_verifier=code_verifier,
        )
    return token


async def exchange_refresh_token(refresh_token: str) -> dict[str, object]:
    """Exchange a refresh token for a new access token (ARCH §6.9)."""
    settings = get_settings()
    client = AsyncOAuth2Client(
        client_id=settings.OIDC_CLIENT_ID,
        client_secret=settings.OIDC_CLIENT_SECRET or None,
    )
    async with client:
        token: dict[str, object] = await client.fetch_token(
            url=settings.OIDC_TOKEN_URL,
            grant_type="refresh_token",
            refresh_token=refresh_token,
        )
    return token
