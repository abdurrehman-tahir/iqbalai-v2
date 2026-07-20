"""Server-side OIDC session storage — state/nonce/PKCE verifier (T-244, ARCH §6.4).

`state` is validated on callback (CSRF); `nonce` is validated against the
id_token; the PKCE `code_verifier` never leaves the server. All three are
generated at ``GET /auth/login`` and stored in Redis (not a cookie) — the
transient ``iqbalai_oidc_session`` cookie only carries a random id that names
*which* Redis entry belongs to this browser, never the secrets themselves.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from authlib.common.security import generate_token

from app.infrastructure.cache.client import get_redis

OIDC_SESSION_COOKIE = "iqbalai_oidc_session"

# Long enough to complete an interactive Authentik login; short enough that a
# stale entry can't be replayed hours later.
_TTL_SECONDS = 600
_KEY_PREFIX = "oidc_session:"

# Relative, same-app paths only — never `//host/...` (protocol-relative) or an
# absolute URL, which would turn the optional `next` param into an open redirect.
_SAFE_NEXT_PATH = re.compile(r"^/(?!/)[A-Za-z0-9\-._~!$&'()*+,;=:@/%]*$")


def safe_next_path(candidate: str | None, default: str) -> str:
    """Return `candidate` if it's a safe relative path, else `default`."""
    if candidate and _SAFE_NEXT_PATH.match(candidate):
        return candidate
    return default


@dataclass(frozen=True)
class OidcSession:
    state: str
    nonce: str
    code_verifier: str
    next_path: str


async def create_oidc_session(next_path: str) -> tuple[str, OidcSession]:
    """Generate state/nonce/PKCE, store them in Redis, return (session_id, session)."""
    session = OidcSession(
        state=generate_token(32),
        nonce=generate_token(32),
        code_verifier=generate_token(64),
        next_path=next_path,
    )
    session_id = generate_token(32)
    redis = get_redis()
    await redis.set(
        f"{_KEY_PREFIX}{session_id}",
        json.dumps(
            {
                "state": session.state,
                "nonce": session.nonce,
                "code_verifier": session.code_verifier,
                "next_path": session.next_path,
            }
        ),
        ex=_TTL_SECONDS,
    )
    return session_id, session


async def consume_oidc_session(session_id: str) -> OidcSession | None:
    """Fetch and delete the stored session — single-use, so a replayed callback
    request (same session cookie, e.g. browser back-button) fails cleanly
    instead of re-running a stale exchange."""
    redis = get_redis()
    key = f"{_KEY_PREFIX}{session_id}"
    raw = await redis.get(key)
    if raw is None:
        return None
    await redis.delete(key)
    data = json.loads(raw)
    return OidcSession(
        state=data["state"],
        nonce=data["nonce"],
        code_verifier=data["code_verifier"],
        next_path=data["next_path"],
    )
