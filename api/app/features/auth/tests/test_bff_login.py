"""BFF auth backend tests — M-07b T-239.

Covers the offline DevAuthBackend (the real AuthentikAuthClient path needs a running
Authentik and is exercised by the T-246 E2E smoke). Verifies: seed credentials
authenticate; wrong password + unknown email both raise the generic
INVALID_CREDENTIALS (no enumeration); refresh round-trips.
"""

from __future__ import annotations

import pytest

from app.core.exceptions import InvalidCredentialsError
from app.infrastructure.authentik.auth import DEV_LOGIN_PASSWORD, DevAuthBackend


async def test_authenticate_returns_tokens_and_claims_for_seed_user() -> None:
    backend = DevAuthBackend()
    pair = await backend.authenticate("teacher@iqbalai.dev", DEV_LOGIN_PASSWORD)

    assert pair.access_token
    assert pair.refresh_token
    assert pair.claims["sub"] == "seed-teacher"
    assert pair.claims["tenant_type"] == "school"


async def test_authenticate_is_case_insensitive_on_email() -> None:
    backend = DevAuthBackend()
    pair = await backend.authenticate("Teacher@IqbalAI.dev", DEV_LOGIN_PASSWORD)
    assert pair.claims["sub"] == "seed-teacher"


async def test_wrong_password_raises_invalid_credentials() -> None:
    backend = DevAuthBackend()
    with pytest.raises(InvalidCredentialsError):
        await backend.authenticate("teacher@iqbalai.dev", "not-the-password")


async def test_unknown_email_raises_same_error_as_wrong_password() -> None:
    # No enumeration: unknown account is indistinguishable from a bad password.
    backend = DevAuthBackend()
    with pytest.raises(InvalidCredentialsError):
        await backend.authenticate("ghost@iqbalai.dev", DEV_LOGIN_PASSWORD)


async def test_refresh_round_trips_for_issued_token() -> None:
    backend = DevAuthBackend()
    pair = await backend.authenticate("admin@iqbalai.dev", DEV_LOGIN_PASSWORD)
    refreshed = await backend.refresh(pair.refresh_token)
    assert refreshed.claims["sub"] == "seed-platform-admin"


async def test_refresh_with_garbage_token_raises() -> None:
    backend = DevAuthBackend()
    with pytest.raises(InvalidCredentialsError):
        await backend.refresh("dev-refresh-nobody")


async def test_confirm_password_reset_succeeds_in_dev() -> None:
    backend = DevAuthBackend()
    await backend.confirm_password_reset("dev-reset-token", "newpassword1")


async def test_confirm_password_reset_rejects_short_password() -> None:
    backend = DevAuthBackend()
    from app.core.exceptions import InvalidResetTokenError

    with pytest.raises(InvalidResetTokenError):
        await backend.confirm_password_reset("dev-reset-token", "short")
