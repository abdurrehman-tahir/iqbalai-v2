"""JWT validation primitives."""

from __future__ import annotations

import structlog
from jose import JWTError, jwt

from app.config import get_settings

logger = structlog.get_logger(__name__)


def decode_jwt(token: str) -> dict[str, object] | None:
    """Decode and validate a JWT issued by Authentik.

    Returns the claims dict on success, None on any validation failure.
    Validation is intentionally lenient in dev (no audience check) — tighten
    per ARCH §6.4 when Authentik is fully wired.
    """
    settings = get_settings()
    try:
        claims: dict[str, object] = jwt.decode(
            token,
            settings.OIDC_JWKS_URL,  # type: ignore[arg-type]
            algorithms=["RS256"],
            options={"verify_aud": False},  # TODO: enable when OIDC fully wired
        )
        return claims
    except JWTError as exc:
        logger.debug("jwt_decode_failed", reason=str(exc))
        return None
