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
    "revoke_refresh_token",
]


def build_authorize_url(
    *,
    redirect_uri: str,
    state: str,
    nonce: str,
    code_verifier: str,
    prompt_login: bool = False,
    login_hint: str | None = None,
) -> str:
    """Build the Authentik authorize redirect (ARCH §6.4 step 2).

    `prompt_login`/`login_hint` preserve the pre-T-245 UX for post-invite and
    post-signup flows (accept-invite, independent/parent signup): force
    Authentik to show the login form pre-filled with the just-verified email,
    rather than silently reusing an unrelated existing SSO session.
    """
    settings = get_settings()
    params = {
        "response_type": "code",
        "client_id": settings.OIDC_CLIENT_ID,
        "redirect_uri": redirect_uri,
        # `iqbalai` is required: the blueprint scope mapping that emits
        # role + tenant_type only runs when this scope is requested. Without
        # it, get_or_create_from_jwt defaults everyone to student.
        "scope": "openid profile email iqbalai",
        "state": state,
        "nonce": nonce,
        "code_challenge": create_s256_code_challenge(code_verifier),
        "code_challenge_method": "S256",
    }
    if prompt_login:
        params["prompt"] = "login"
    if login_hint:
        params["login_hint"] = login_hint
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


async def revoke_refresh_token(refresh_token: str) -> None:
    """Revoke the refresh token at Authentik (ARCH §6.8, RFC 7009).

    Best-effort by design: the caller decides whether a failure here should
    block logout. Our own state is already torn down by the time this would
    be called — the opaque `iqbalai_refresh` reference is deleted the moment
    it's resolved (refresh_session.resolve_and_rotate), so the token can't be
    replayed through our own /refresh endpoint even if Authentik's revoke
    call fails or times out.
    """
    settings = get_settings()
    client = AsyncOAuth2Client(
        client_id=settings.OIDC_CLIENT_ID,
        client_secret=settings.OIDC_CLIENT_SECRET or None,
    )
    async with client:
        await client.revoke_token(
            settings.OIDC_REVOKE_URL,
            token=refresh_token,
            token_type_hint="refresh_token",
        )
