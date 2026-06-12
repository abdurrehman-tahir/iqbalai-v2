"""JWT validation primitives."""

from __future__ import annotations

import time
from typing import Any

import httpx
import structlog
from jose import JWTError, jwk, jwt

from app.config import get_settings

logger = structlog.get_logger(__name__)

_jwks_cache: dict[str, Any] | None = None
_jwks_cache_expires_at: float = 0.0
_JWKS_TTL_SECONDS = 300


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
    """Decode and validate a JWT issued by Authentik.

    Returns the claims dict on success, None on any validation failure.
    Validation is intentionally lenient in dev (no audience check) — tighten
    per ARCH §6.4 when Authentik is fully wired.
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
            algorithms=["RS256"],
            options={"verify_aud": False, "verify_iss": False},
        )
        return claims
    except (JWTError, httpx.HTTPError, httpx.TransportError) as exc:
        logger.debug("jwt_decode_failed", reason=str(exc))
        return None
