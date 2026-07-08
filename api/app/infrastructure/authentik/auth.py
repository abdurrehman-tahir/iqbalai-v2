"""Authentik BFF auth backend — server-side credential exchange (M-07b T-239).

Parallel to the user-lifecycle ``AuthentikClient`` (client.py). This module is the
single chokepoint where end-user credentials are validated: they hit only the FastAPI
backend, never the browser. We exchange ``email`` + ``password`` for Authentik tokens
using the OAuth password grant on the **confidential** ``OIDC_CLIENT_ID`` (never the
public SPA client — ARCH §6.4 amendment A-003, T-239 note).

Password reset ``confirm`` runs Authentik's recovery flow executor server-side so the
user completes reset on our custom ``/login/reset-password`` surface (T-243).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol
from urllib.parse import urlencode

import httpx
import structlog

from app.config import get_settings
from app.core.exceptions import (
    EmailNotVerifiedError,
    InvalidCredentialsError,
    InvalidResetTokenError,
    RateLimitedError,
)
from app.core.security import decode_jwt

logger = structlog.get_logger(__name__)

# Shared password accepted by the dev backend for every known seed user, so
# `scripts/seed_dev.py` accounts can log in without a running Authentik (tests +
# offline dev). Never used by the real backend.
DEV_LOGIN_PASSWORD = "devpassword"


@dataclass
class TokenPair:
    """Result of a successful credential exchange.

    ``claims`` are the decoded access-token claims (real backend) or the seeded
    identity (dev backend) so the login endpoint can run post-login without a
    second decode round-trip.
    """

    access_token: str
    refresh_token: str
    expires_in: int
    claims: dict[str, object] = field(default_factory=dict)


class AuthBackendProtocol(Protocol):
    async def authenticate(self, email: str, password: str) -> TokenPair: ...

    async def refresh(self, refresh_token: str) -> TokenPair: ...

    async def revoke(self, refresh_token: str) -> None: ...

    async def request_password_reset(self, email: str) -> None: ...

    async def confirm_password_reset(self, token: str, new_password: str) -> None: ...


class AuthentikAuthClient:
    """Production BFF backend — talks to Authentik's OAuth token endpoint."""

    def __init__(
        self,
        token_url: str,
        client_id: str,
        client_secret: str,
    ) -> None:
        self._token_url = token_url
        self._client_id = client_id
        self._client_secret = client_secret

    async def _token_request(self, form: dict[str, str]) -> dict[str, object]:
        form = {
            **form,
            "client_id": self._client_id,
            "client_secret": self._client_secret,
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                self._token_url,
                data=form,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )

        if resp.status_code == 429:
            raise RateLimitedError()

        if resp.is_success:
            return resp.json()

        # Map Authentik OAuth errors to structured app errors without leaking detail.
        detail = ""
        try:
            body = resp.json()
            detail = str(body.get("error_description", body.get("error", "")))
        except ValueError:
            detail = resp.text

        logger.info("bff_token_request_rejected", status_code=resp.status_code, detail=detail[:200])

        lowered = detail.lower()
        if "verif" in lowered:  # e.g. "email not verified"
            raise EmailNotVerifiedError()
        # invalid_grant / invalid credentials / inactive user → generic (no enumeration).
        raise InvalidCredentialsError()

    async def authenticate(self, email: str, password: str) -> TokenPair:
        data = await self._token_request(
            {
                "grant_type": "password",
                "username": email,
                "password": password,
                "scope": "openid profile email offline_access",
            }
        )
        return await self._to_token_pair(data)

    async def refresh(self, refresh_token: str) -> TokenPair:
        data = await self._token_request(
            {
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            }
        )
        return await self._to_token_pair(data)

    async def revoke(self, refresh_token: str) -> None:
        revoke_url = self._token_url.replace("/token/", "/revoke/")
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                revoke_url,
                data={
                    "token": refresh_token,
                    "token_type_hint": "refresh_token",
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        # RFC 7009: the revoke endpoint returns 200 even for unknown tokens. Log
        # non-2xx but do not fail logout — cookies are cleared regardless.
        if not resp.is_success:
            logger.warning("bff_token_revoke_non_2xx", status_code=resp.status_code)

    async def request_password_reset(self, email: str) -> None:
        # Best-effort trigger of Authentik's recovery email. Deliberately swallows all
        # errors so the API response is identical whether or not the account exists
        # (no enumeration — T-240 acceptance #4). Full custom reset surface = T-243.
        settings = get_settings()
        if not settings.AUTHENTIK_API_TOKEN:
            logger.warning(
                "bff_password_reset_no_api_token",
                hint="Set AUTHENTIK_API_TOKEN so recovery emails are sent by Authentik",
            )
            return
        try:
            base = settings.AUTHENTIK_API_URL.rstrip("/")
            headers = {"Authorization": f"Bearer {settings.AUTHENTIK_API_TOKEN}"}
            async with httpx.AsyncClient(timeout=30.0) as client:
                found = await client.get(
                    f"{base}/core/users/", params={"email": email}, headers=headers
                )
                found.raise_for_status()
                results = found.json().get("results", [])
                if not results:
                    return
                pk = results[0]["pk"]
                await client.post(f"{base}/core/users/{pk}/recovery_email/", headers=headers)
        except (httpx.HTTPError, KeyError, ValueError, IndexError) as exc:
            logger.info("bff_password_reset_trigger_failed", reason=str(exc))

    async def confirm_password_reset(self, token: str, new_password: str) -> None:
        """Complete a password reset via Authentik's recovery flow executor."""
        settings = get_settings()
        slug = settings.AUTHENTIK_RECOVERY_FLOW_SLUG
        base = settings.AUTHENTIK_API_URL.rstrip("/")
        executor_url = f"{base}/flows/executor/{slug}/"
        query_string = urlencode({"token": token.strip()})

        async with httpx.AsyncClient(timeout=30.0, follow_redirects=False) as client:
            resp = await client.get(executor_url, params={"query": query_string})
            for _ in range(12):
                if resp.status_code in (301, 302, 303, 307, 308):
                    return
                if not resp.is_success:
                    raise InvalidResetTokenError()
                try:
                    body = resp.json()
                except ValueError:
                    raise InvalidResetTokenError() from None

                component = str(body.get("component", ""))
                if component == "xak-flow-redirect":
                    return
                if component == "ak-stage-access-denied":
                    raise InvalidResetTokenError()

                if component in ("ak-stage-user-password", "ak-stage-prompt"):
                    payload: dict[str, str] = {
                        "component": component,
                        "password": new_password,
                    }
                    if component == "ak-stage-user-password":
                        payload["password_repeat"] = new_password
                    resp = await client.post(
                        executor_url,
                        params={"query": query_string},
                        json=payload,
                    )
                    continue

                logger.warning("bff_recovery_unknown_stage", component=component)
                raise InvalidResetTokenError()

        raise InvalidResetTokenError()

    async def _to_token_pair(self, data: dict[str, object]) -> TokenPair:
        access = str(data.get("access_token", ""))
        refresh = str(data.get("refresh_token", ""))
        expires_in = int(data.get("expires_in", 0) or 0)
        if not access:
            raise InvalidCredentialsError()
        claims = await decode_jwt(access)
        if claims is None:
            # Token issued but unverifiable (JWKS mismatch) — treat as auth failure
            # rather than proceed with an unvalidated identity.
            logger.error("bff_access_token_undecodable")
            raise InvalidCredentialsError()
        return TokenPair(
            access_token=access,
            refresh_token=refresh,
            expires_in=expires_in,
            claims=claims,
        )


class DevAuthBackend:
    """Offline/test backend: accepts DEV_LOGIN_PASSWORD for seeded users.

    Maps email → (authentik sub, tenant_type) so the login endpoint can build claims
    without a running Authentik. Tokens are opaque dev placeholders — never decoded.
    """

    # email → (authentik_id/sub, tenant_type). Mirrors scripts/seed_dev.py.
    _DEFAULT_USERS: dict[str, tuple[str, str]] = {
        "admin@iqbalai.dev": ("seed-platform-admin", "school"),
        "district.admin@iqbalai.dev": ("seed-district-admin", "school"),
        "school.admin@iqbalai.dev": ("seed-school-admin", "school"),
        "coordinator@iqbalai.dev": ("seed-coordinator", "school"),
        "teacher@iqbalai.dev": ("seed-teacher", "school"),
        "student@iqbalai.dev": ("seed-student", "school"),
    }

    def __init__(self, users: dict[str, tuple[str, str]] | None = None) -> None:
        self._users = users if users is not None else dict(self._DEFAULT_USERS)

    async def authenticate(self, email: str, password: str) -> TokenPair:
        entry = self._users.get(email.strip().lower())
        if entry is None or password != DEV_LOGIN_PASSWORD:
            raise InvalidCredentialsError()
        sub, tenant_type = entry
        claims: dict[str, object] = {"sub": sub, "email": email, "tenant_type": tenant_type}
        logger.info("dev_bff_authenticate", email=email, sub=sub)
        return TokenPair(
            access_token=f"dev-access-{sub}",
            refresh_token=f"dev-refresh-{sub}",
            expires_in=get_settings().ACCESS_COOKIE_MAX_AGE,
            claims=claims,
        )

    async def refresh(self, refresh_token: str) -> TokenPair:
        sub = refresh_token.removeprefix("dev-refresh-")
        entry = next(
            ((s, t) for e, (s, t) in self._users.items() if s == sub),
            None,
        )
        if entry is None:
            raise InvalidCredentialsError()
        _sub, tenant_type = entry
        claims: dict[str, object] = {"sub": sub, "tenant_type": tenant_type}
        return TokenPair(
            access_token=f"dev-access-{sub}",
            refresh_token=refresh_token,
            expires_in=get_settings().ACCESS_COOKIE_MAX_AGE,
            claims=claims,
        )

    async def revoke(self, refresh_token: str) -> None:
        logger.info("dev_bff_revoke")

    async def request_password_reset(self, email: str) -> None:
        logger.info("dev_bff_password_reset_requested", email=email)

    async def confirm_password_reset(self, token: str, new_password: str) -> None:
        if not token.strip() or len(new_password) < 8:
            raise InvalidResetTokenError()
        logger.info("dev_bff_password_reset_confirmed", token_prefix=token[:8])


_dev_auth_backend: DevAuthBackend | None = None


def get_auth_backend() -> AuthBackendProtocol:
    """Return the process-wide BFF auth backend (dev stub when no Authentik API token)."""
    global _dev_auth_backend
    settings = get_settings()
    if not settings.AUTHENTIK_API_TOKEN:
        if _dev_auth_backend is None:
            logger.warning(
                "bff_dev_auth_backend_active",
                hint="Credentials validated against seed users only — set AUTHENTIK_API_TOKEN",
            )
            _dev_auth_backend = DevAuthBackend()
        return _dev_auth_backend
    return AuthentikAuthClient(
        settings.OIDC_TOKEN_URL,
        settings.OIDC_CLIENT_ID,
        settings.OIDC_CLIENT_SECRET,
    )
