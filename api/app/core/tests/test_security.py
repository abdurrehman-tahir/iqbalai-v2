"""JWT validation tests — T-241 (ARCH §6.5: ES256+RS256, iss/aud, JWKS TTL)."""

from __future__ import annotations

import time
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from jose import jwk as jose_jwk
from jose import jwt as jose_jwt

from app.config import Settings
from app.core import security

_KID = "test-key-1"
_ISSUER = "http://localhost:9000/application/o/iqbalai/"
_AUDIENCE = "iqbalai-api"


def _generate_es256_keypair() -> tuple[str, dict[str, Any]]:
    """Return (private PEM, public JWK dict) for an ES256 (P-256) test keypair."""
    private_key = ec.generate_private_key(ec.SECP256R1())
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    public_pem = (
        private_key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )
    public_jwk: dict[str, Any] = jose_jwk.construct(public_pem, algorithm="ES256").to_dict()
    public_jwk["kid"] = _KID
    public_jwk["alg"] = "ES256"
    return private_pem, public_jwk


def _make_token(private_pem: str, **claim_overrides: Any) -> str:
    now = int(time.time())
    claims: dict[str, Any] = {
        "sub": "user-123",
        "iss": _ISSUER,
        "aud": _AUDIENCE,
        "iat": now,
        "exp": now + 300,
    }
    claims.update(claim_overrides)
    return str(jose_jwt.encode(claims, private_pem, algorithm="ES256", headers={"kid": _KID}))


@pytest.fixture(autouse=True)
def _reset_jwks_cache() -> None:
    security._jwks_cache = None
    security._jwks_cache_expires_at = 0.0


@pytest.fixture()
def keypair() -> tuple[str, dict[str, Any]]:
    return _generate_es256_keypair()


def _settings_override() -> Settings:
    return Settings(OIDC_ISSUER_URL=_ISSUER, OIDC_CLIENT_ID=_AUDIENCE)


@pytest.mark.asyncio
async def test_valid_es256_token_is_accepted(keypair: tuple[str, dict[str, Any]]) -> None:
    private_pem, public_jwk = keypair
    token = _make_token(private_pem)

    with (
        patch("app.core.security._fetch_jwks", AsyncMock(return_value={"keys": [public_jwk]})),
        patch("app.core.security.get_settings", _settings_override),
    ):
        claims = await security.decode_jwt(token)

    assert claims is not None
    assert claims["sub"] == "user-123"


@pytest.mark.asyncio
async def test_wrong_issuer_returns_none(keypair: tuple[str, dict[str, Any]]) -> None:
    private_pem, public_jwk = keypair
    token = _make_token(private_pem, iss="http://evil.example/")

    with (
        patch("app.core.security._fetch_jwks", AsyncMock(return_value={"keys": [public_jwk]})),
        patch("app.core.security.get_settings", _settings_override),
    ):
        claims = await security.decode_jwt(token)

    assert claims is None


@pytest.mark.asyncio
async def test_wrong_audience_returns_none(keypair: tuple[str, dict[str, Any]]) -> None:
    private_pem, public_jwk = keypair
    token = _make_token(private_pem, aud="some-other-client")

    with (
        patch("app.core.security._fetch_jwks", AsyncMock(return_value={"keys": [public_jwk]})),
        patch("app.core.security.get_settings", _settings_override),
    ):
        claims = await security.decode_jwt(token)

    assert claims is None


@pytest.mark.asyncio
async def test_expired_token_returns_none(keypair: tuple[str, dict[str, Any]]) -> None:
    private_pem, public_jwk = keypair
    now = int(time.time())
    # Well past both the token's own expiry and the 30s leeway.
    token = _make_token(private_pem, iat=now - 600, exp=now - 600)

    with (
        patch("app.core.security._fetch_jwks", AsyncMock(return_value={"keys": [public_jwk]})),
        patch("app.core.security.get_settings", _settings_override),
    ):
        claims = await security.decode_jwt(token)

    assert claims is None


@pytest.mark.asyncio
async def test_jwks_cache_honors_one_hour_ttl(
    keypair: tuple[str, dict[str, Any]], monkeypatch: pytest.MonkeyPatch
) -> None:
    _, public_jwk = keypair
    fake_now = {"t": 1_000_000.0}
    # security.py's own `time` import is the actual monotonic() call target.
    monkeypatch.setattr(security.time, "monotonic", lambda: fake_now["t"])  # type: ignore[attr-defined]

    call_count = 0

    class _FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, Any]:
            return {"keys": [public_jwk]}

    class _FakeAsyncClient:
        async def __aenter__(self) -> "_FakeAsyncClient":
            return self

        async def __aexit__(self, *exc_info: object) -> None:
            return None

        async def get(self, url: str) -> _FakeResponse:
            nonlocal call_count
            call_count += 1
            return _FakeResponse()

    with patch("app.core.security.httpx.AsyncClient", lambda timeout=10.0: _FakeAsyncClient()):
        await security._fetch_jwks("http://jwks.example/")
        assert call_count == 1

        # Still within the 1h TTL: cache hit, no re-fetch.
        fake_now["t"] += 3599
        await security._fetch_jwks("http://jwks.example/")
        assert call_count == 1

        # Past the 1h TTL: cache miss, re-fetches.
        fake_now["t"] += 2
        await security._fetch_jwks("http://jwks.example/")
        assert call_count == 2
