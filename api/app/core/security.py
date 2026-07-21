"""JWT validation primitives."""

from __future__ import annotations

import hashlib
import time
from typing import Any

import httpx
import structlog
from jose import JWTError, jwk, jwt

from app.config import get_settings
from app.infrastructure.cache.client import get_redis

logger = structlog.get_logger(__name__)

_BLACKLIST_KEY_PREFIX = "jti_blacklist:"

_jwks_cache: dict[str, Any] | None = None
_jwks_cache_expires_at: float = 0.0
_JWKS_TTL_SECONDS = 3600  # 1h per ARCH §6.5


async def _fetch_jwks(jwks_url: str) -> dict[str, Any]:
    """Fetch and cache JWKS from Authentik (async — must not block the event loop)."""
    global _jwks_cache, _jwks_cache_expires_at

    now = time.monotonic()
    if _jwks_cache is not None and now < _jwks_cache_expires_at:
        return _jwks_cache

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(jwks_url)
        response.raise_for_status()
        fresh: dict[str, Any] = response.json()
        _jwks_cache = fresh
        _jwks_cache_expires_at = now + _JWKS_TTL_SECONDS
        return fresh


def _signing_key_for_token(token: str, jwks: dict[str, Any]) -> Any | None:
    """Resolve the RSA public key for the token's kid."""
    try:
        header = jwt.get_unverified_header(token)
    except JWTError:
        return None

    kid = header.get("kid")
    keys = jwks.get("keys", [])
    if not isinstance(keys, list):
        return None

    for key_data in keys:
        if not isinstance(key_data, dict):
            continue
        if kid is None or key_data.get("kid") == kid:
            return jwk.construct(key_data)
    return None


async def decode_jwt(token: str) -> dict[str, object] | None:
    """Decode and validate a JWT issued by Authentik per ARCH §6.5.

    Returns the claims dict on success, None on any validation failure
    (missing/malformed token, bad signature, expiry, issuer mismatch,
    audience mismatch, or a missing required claim — all map to 401 at
    the caller). ES256 is Authentik's default signing algorithm; RS256
    is kept as a locked fallback. Issuer/audience are verified against
    the configured Authentik instance — never skipped.
    """
    settings = get_settings()
    try:
        jwks = await _fetch_jwks(settings.OIDC_JWKS_URL)
        signing_key = _signing_key_for_token(token, jwks)
        if signing_key is None:
            logger.debug("jwt_decode_failed", reason="no_matching_signing_key")
            return None

        claims: dict[str, object] = jwt.decode(
            token,
            signing_key,
            algorithms=["ES256", "RS256"],
            audience=settings.OIDC_CLIENT_ID,
            issuer=settings.OIDC_ISSUER_URL,
            options={
                "require": ["exp", "iat", "sub", "iss", "aud"],
                # Authentik and the API VMs are NTP-synced; 30s is generous (§6.5).
                "leeway": 30,
            },
        )
        return claims
    except (JWTError, httpx.HTTPError, httpx.TransportError) as exc:
        logger.debug("jwt_decode_failed", reason=str(exc))
        return None


def blacklist_id_for(token: str, claims: dict[str, object]) -> str:
    """Stable identifier for `token` in the logout blacklist (ARCH §6.8).

    Prefers the JWT's `jti` claim (the spec-intended mechanism the ARCH
    section names). `jti` isn't in decode_jwt's required-claims list — this
    codebase can't assert Authentik always issues one — so when it's absent,
    falls back to a SHA-256 hash of the raw token string. Both are stable
    (same token → same id every time), which is all the blacklist needs:
    the logout route and AuthMiddleware must independently derive the same
    id from the same token to agree on a hit.
    """
    jti = claims.get("jti")
    if isinstance(jti, str) and jti:
        return jti
    return hashlib.sha256(token.encode()).hexdigest()


async def is_jti_blacklisted(blacklist_id: str) -> bool:
    """True if `blacklist_id` was blacklisted at logout and hasn't expired."""
    redis = get_redis()
    return bool(await redis.exists(f"{_BLACKLIST_KEY_PREFIX}{blacklist_id}"))


async def blacklist_jti(blacklist_id: str, ttl_seconds: int) -> None:
    """Blacklist `blacklist_id` until the token would have naturally expired.

    A non-positive TTL means the token is already expired (or within the
    validator's clock-skew leeway of it) — decode_jwt would reject it anyway,
    so there's nothing worth blacklisting.
    """
    if ttl_seconds <= 0:
        return
    redis = get_redis()
    await redis.set(f"{_BLACKLIST_KEY_PREFIX}{blacklist_id}", "1", ex=ttl_seconds)
