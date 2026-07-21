"""Server-owned OIDC redirect-flow primitives (ARCH §6.4 and §6.17)."""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
from dataclasses import dataclass
from urllib.parse import urlencode

import httpx

from app.config import get_settings
from app.core.security import decode_jwt
from app.infrastructure.cache.client import get_redis

_STATE_TTL_SECONDS = 600
_REFRESH_TTL_SECONDS = 30 * 24 * 60 * 60


@dataclass(frozen=True)
class OidcCallbackTokens:
    access_token: str
    refresh_token: str
    id_token: str


def _url_token() -> str:
    return secrets.token_urlsafe(32)


def _pkce_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def _endpoint(name: str) -> str:
    settings = get_settings()
    return f"{settings.OIDC_ISSUER_URL.rstrip('/')}/{name}/"


def safe_next_path(next_path: str | None) -> str:
    """Permit only an in-app relative path; never redirect an auth flow off-site."""
    if next_path and next_path.startswith("/") and not next_path.startswith("//"):
        return next_path
    return "/"


async def start_login(next_path: str | None) -> tuple[str, str]:
    """Persist state/nonce/PKCE server-side and return transient id plus redirect URL."""
    settings = get_settings()
    transient_id = _url_token()
    state = _url_token()
    nonce = _url_token()
    verifier = _url_token()
    record = {
        "state": state,
        "nonce": nonce,
        "verifier": verifier,
        "next": safe_next_path(next_path),
    }
    await get_redis().setex(
        f"oidc:state:{transient_id}", _STATE_TTL_SECONDS, json.dumps(record)
    )
    params = urlencode(
        {
            "client_id": settings.OIDC_CLIENT_ID,
            "response_type": "code",
            "scope": "openid profile email",
            "redirect_uri": f"{settings.APP_URL.rstrip('/')}/api/v1/auth/callback",
            "state": state,
            "nonce": nonce,
            "code_challenge": _pkce_challenge(verifier),
            "code_challenge_method": "S256",
        }
    )
    return transient_id, f"{_endpoint('authorize')}?{params}"


async def complete_login(transient_id: str | None, state: str | None, code: str | None) -> tuple[
    OidcCallbackTokens, str
]:
    """Validate state and nonce, exchange the authorization code server-side."""
    if not transient_id or not state or not code:
        raise ValueError("Missing OIDC callback parameters")
    redis = get_redis()
    raw = await redis.getdel(f"oidc:state:{transient_id}")
    if raw is None:
        raise ValueError("OIDC login state is missing or expired")
    record = json.loads(raw)
    if not secrets.compare_digest(state, str(record["state"])):
        raise ValueError("OIDC state validation failed")

    settings = get_settings()
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            _endpoint("token"),
            data={
                "grant_type": "authorization_code",
                "code": code,
                "client_id": settings.OIDC_CLIENT_ID,
                "client_secret": settings.OIDC_CLIENT_SECRET,
                "redirect_uri": f"{settings.APP_URL.rstrip('/')}/api/v1/auth/callback",
                "code_verifier": record["verifier"],
            },
        )
        response.raise_for_status()
    payload = response.json()
    access_token = str(payload.get("access_token", ""))
    refresh_token = str(payload.get("refresh_token", ""))
    id_token = str(payload.get("id_token", ""))
    if not access_token or not refresh_token or not id_token:
        raise ValueError("OIDC token response is incomplete")
    id_claims = await decode_jwt(id_token)
    nonce = str(id_claims.get("nonce", "")) if id_claims else ""
    if not id_claims or not secrets.compare_digest(nonce, record["nonce"]):
        raise ValueError("OIDC nonce validation failed")
    return OidcCallbackTokens(access_token, refresh_token, id_token), str(record["next"])


async def save_refresh_token(refresh_token: str) -> str:
    """Store an IdP refresh token behind an opaque, rotating browser reference."""
    reference = _url_token()
    await get_redis().setex(f"oidc:refresh:{reference}", _REFRESH_TTL_SECONDS, refresh_token)
    return reference


async def rotate_refresh_token(reference: str) -> tuple[str, str]:
    """Consume an opaque reference and replace it with a rotated token reference."""
    redis = get_redis()
    refresh_token = await redis.getdel(f"oidc:refresh:{reference}")
    if refresh_token is None:
        raise ValueError("Refresh session is invalid or expired")
    settings = get_settings()
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            _endpoint("token"),
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": settings.OIDC_CLIENT_ID,
                "client_secret": settings.OIDC_CLIENT_SECRET,
            },
        )
        response.raise_for_status()
    payload = response.json()
    access_token = str(payload.get("access_token", ""))
    rotated_refresh = str(payload.get("refresh_token", ""))
    if not access_token or not rotated_refresh:
        raise ValueError("OIDC refresh response is incomplete")
    return access_token, await save_refresh_token(rotated_refresh)


async def revoke_refresh_token(reference: str | None) -> None:
    if not reference:
        return
    refresh_token = await get_redis().getdel(f"oidc:refresh:{reference}")
    if not refresh_token:
        return
    settings = get_settings()
    async with httpx.AsyncClient(timeout=10.0) as client:
        await client.post(
            _endpoint("revoke"),
            data={
                "token": refresh_token,
                "token_type_hint": "refresh_token",
                "client_id": settings.OIDC_CLIENT_ID,
                "client_secret": settings.OIDC_CLIENT_SECRET,
            },
        )
