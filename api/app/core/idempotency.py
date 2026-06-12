"""Idempotency-Key support for resource-creating endpoints (ARCH §5.9).

A client may send an ``Idempotency-Key`` header on a POST so that retries (network
flakiness, double-clicks) do not create duplicate resources. The contract:

* **First use** of a key — the request runs normally and its response is cached for
  24h under that key.
* **Replay** with the *same* key and the *same* request body — the cached response
  is returned without re-running the handler.
* **Reuse** of the same key with a *different* request body — ``409
  IDEMPOTENCY_KEY_MISMATCH`` (a key must identify exactly one logical operation).

State lives in Redis (24h TTL) via the cache chokepoint. The key is namespaced by
tenant so two tenants can independently use the same client-chosen key.

If no ``Idempotency-Key`` header is supplied the dependency returns ``None`` and the
endpoint runs without idempotency protection.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

import structlog
from fastapi import Depends, Request

from app.core.dependencies import get_current_user
from app.core.exceptions import IdempotencyKeyMismatchError
from app.infrastructure.cache.client import get_redis

logger = structlog.get_logger(__name__)

# 24h, per ARCH §5.9.
_TTL_SECONDS = 24 * 60 * 60


class IdempotencyContext:
    """Per-request idempotency state for one ``Idempotency-Key``.

    Holds the two Redis keys (the body-hash guard and the cached response) and the
    hash of the current request body. ``begin()`` enforces the mismatch rule;
    ``cached_response()`` returns a prior response on replay; ``store_response()``
    caches the response after a successful first run.
    """

    def __init__(self, namespace_key: str, body_hash: str) -> None:
        self._redis = get_redis()
        self._hash_key = f"idem:hash:{namespace_key}"
        self._response_key = f"idem:resp:{namespace_key}"
        self._body_hash = body_hash
        self.is_replay = False

    async def begin(self) -> None:
        """Claim the key for this body, or raise on a mismatched reuse.

        Uses ``SET NX`` so the first caller atomically wins the key. A subsequent
        caller with a different body hash gets ``409``; one with the same body hash
        is flagged as a replay (its response is served from cache).
        """
        created = await self._redis.set(self._hash_key, self._body_hash, ex=_TTL_SECONDS, nx=True)
        if created:
            return
        stored = await self._redis.get(self._hash_key)
        if stored is not None and stored != self._body_hash:
            logger.warning("idempotency_key_mismatch", key=self._hash_key)
            raise IdempotencyKeyMismatchError()
        self.is_replay = True

    async def cached_response(self) -> dict[str, Any] | None:
        """Return the cached response for this key, if one was stored."""
        raw = await self._redis.get(self._response_key)
        if raw is None:
            return None
        loaded: dict[str, Any] = json.loads(raw)
        return loaded

    async def store_response(self, response: dict[str, Any]) -> None:
        """Cache the handler's response under this key for the TTL window."""
        await self._redis.set(self._response_key, json.dumps(response), ex=_TTL_SECONDS)


async def idempotency_key(
    request: Request,
    claims: dict[str, object] = Depends(get_current_user),
) -> IdempotencyContext | None:
    """FastAPI dependency: build (and pre-check) idempotency state for a request.

    Returns ``None`` when no ``Idempotency-Key`` header is present. Reading the body
    here is safe — Starlette caches it, so request-model parsing still works.
    """
    key = request.headers.get("Idempotency-Key")
    if not key:
        return None

    body = await request.body()
    body_hash = hashlib.sha256(body).hexdigest()
    # Namespace by tenant so the same client-chosen key in two tenants never collides.
    tenant = str(claims.get("tenant_id") or claims.get("tenant_type") or "global")
    ctx = IdempotencyContext(namespace_key=f"{tenant}:{key}", body_hash=body_hash)
    await ctx.begin()
    return ctx
