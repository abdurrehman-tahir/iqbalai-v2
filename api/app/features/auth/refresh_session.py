"""Opaque refresh-token reference storage (T-244, ARCH §6.4/§6.9).

The ``iqbalai_refresh`` cookie never carries Authentik's real refresh token —
it carries a random opaque reference that maps, server-side only, to the real
token in Redis. If the cookie value leaks, it's useless without this mapping.
Every successful refresh rotates both the mapping and the opaque reference
(single-use — ``resolve_and_rotate`` deletes the entry it reads), so a
replayed reference fails instead of quietly reusing a stale session.
"""

from __future__ import annotations

from authlib.common.security import generate_token

from app.infrastructure.cache.client import get_redis

# 30d, matches the iqbalai_refresh cookie Max-Age (ARCH §6.4).
_TTL_SECONDS = 30 * 24 * 60 * 60
_KEY_PREFIX = "refresh_ref:"


async def store_refresh_token(authentik_refresh_token: str) -> str:
    """Store `authentik_refresh_token` under a new opaque reference; return it."""
    opaque_ref: str = generate_token(48)
    redis = get_redis()
    await redis.set(f"{_KEY_PREFIX}{opaque_ref}", authentik_refresh_token, ex=_TTL_SECONDS)
    return opaque_ref


async def resolve_and_rotate(opaque_ref: str) -> str | None:
    """Return the real refresh token for `opaque_ref`, deleting the mapping.

    The caller must call `store_refresh_token` again with whatever token
    Authentik returns (even if unchanged) to obtain a fresh reference for the
    next cookie — this function never re-stores on its own.
    """
    redis = get_redis()
    key = f"{_KEY_PREFIX}{opaque_ref}"
    token: str | None = await redis.get(key)
    if token is None:
        return None
    await redis.delete(key)
    return token
