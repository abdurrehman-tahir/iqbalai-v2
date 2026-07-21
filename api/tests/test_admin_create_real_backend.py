"""Phase 1 — real-backend create contract tests.

Hits the live FastAPI app (TestClient over create_app()) with JWT auth mocked
only at the middleware boundary. Service/repository/validation are real.

These tests assert the UI payloads succeed (201). They fail red until the
frontend payloads are aligned with the OpenAPI create schemas.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

import app.core.dependencies as deps_mod
import app.db.engine as engine_mod
import app.db.session as session_mod
from app.config import get_settings
from app.main import create_app
from tests.fixtures.frontend_payloads import (
    EXAM_SYLLABUS_CREATE_FROM_UI,
    SUBSCRIPTION_TIER_CREATE_FROM_UI,
)

_PLATFORM_ADMIN_CLAIMS: dict[str, object] = {
    "sub": "phase1-test-admin",
    "role": "platform_admin",
    "email": "admin@phase1.test",
}

REAL_BACKEND_URL = os.environ.get("REAL_BACKEND_URL", "http://localhost:8000/api/v1")


def _resolve_test_db_url() -> str:
    """Prefer explicit CI/local env, then macOS compose heuristics."""
    override = os.environ.get("TEST_DB_URL") or os.environ.get("DB_URL")
    if override:
        return override

    import subprocess

    for iface in ("en0", "en1"):
        try:
            ip = subprocess.check_output(
                ["ipconfig", "getifaddr", iface],
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            continue
        if ip:
            user = os.environ.get("POSTGRES_USER", "iqbalai")
            password = os.environ.get("POSTGRES_PASSWORD", "change_me_in_production")
            db = os.environ.get("POSTGRES_DB", "iqbalai")
            return f"postgresql+asyncpg://{user}:{password}@{ip}:5432/{db}"

    user = os.environ.get("POSTGRES_USER", "iqbalai")
    password = os.environ.get("POSTGRES_PASSWORD", "change_me_in_production")
    db = os.environ.get("POSTGRES_DB", "iqbalai")
    return f"postgresql+asyncpg://{user}:{password}@127.0.0.1:5432/{db}"


async def _postgres_reachable(db_url: str) -> bool:
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(db_url, pool_pre_ping=True)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except OSError:
        return False
    except Exception:
        return False
    finally:
        await engine.dispose()


def _rebind_async_session_factory() -> None:
    """Point FastAPI DB deps at the current engine (import-time factory is stale)."""
    import app.core.middleware as middleware_mod

    factory = async_sessionmaker(
        bind=engine_mod.get_engine(),
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
    session_mod.async_session_factory = factory
    deps_mod.async_session_factory = factory
    middleware_mod.async_session_factory = factory


async def _dispose_engine() -> None:
    engine = engine_mod._engine
    if engine is not None:
        await engine.dispose()
    engine_mod._engine = None


@pytest.fixture()
async def authed_client(monkeypatch: pytest.MonkeyPatch) -> AsyncGenerator[AsyncClient, None]:
    """FastAPI app with platform_admin JWT claims injected at middleware."""
    db_url = _resolve_test_db_url()
    if not await _postgres_reachable(db_url):
        pytest.skip("Postgres not reachable at configured DB_URL (need compose or CI service)")

    monkeypatch.setenv("DB_URL", db_url)
    get_settings.cache_clear()
    await _dispose_engine()
    _rebind_async_session_factory()

    # Auth is mocked only at the middleware boundary (see module docstring): both
    # decode_jwt AND the jti-denylist check live there. The denylist check hits
    # Redis (T-246), which the backend-tests job intentionally does not run — mock
    # it to a miss so the real service/repository/validation path stays exercised.
    with (
        patch(
            "app.core.middleware.decode_jwt",
            new_callable=AsyncMock,
            return_value=_PLATFORM_ADMIN_CLAIMS,
        ),
        patch(
            "app.core.middleware.is_jti_blacklisted",
            new_callable=AsyncMock,
            return_value=False,
        ),
    ):
        transport = ASGITransport(app=create_app())
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client

    get_settings.cache_clear()
    await _dispose_engine()


def _assert_create_succeeds(response: httpx.Response, resource: str) -> None:
    assert response.status_code == 201, (
        f"{resource} create must succeed with UI payload; "
        f"got {response.status_code}: {response.text}"
    )
    body = response.json()
    assert body.get("data") is not None, f"{resource} response missing data envelope"
    assert body.get("message") == "ok", f"{resource} response missing message envelope"


# ── In-process real routes (require Postgres) ───────────────────────────────


async def test_exam_syllabus_create_accepts_ui_payload(authed_client: AsyncClient) -> None:
    """UI payload should create a syllabus — fails until exam_board is sent."""
    payload = {
        **EXAM_SYLLABUS_CREATE_FROM_UI,
        "name": f"{EXAM_SYLLABUS_CREATE_FROM_UI['name']} {uuid.uuid4().hex[:8]}",
    }
    response = await authed_client.post(
        "/api/v1/admin/exam-syllabi/",
        json=payload,
        cookies={"iqbalai_access": "phase1-test-token"},
    )
    _assert_create_succeeds(response, "exam_syllabus")


async def test_subscription_tier_create_accepts_ui_payload(authed_client: AsyncClient) -> None:
    """UI payload should create a tier — fails until slug + applies_to are sent."""
    payload = {
        **SUBSCRIPTION_TIER_CREATE_FROM_UI,
        "slug": f"school-basic-{uuid.uuid4().hex[:8]}",
    }
    response = await authed_client.post(
        "/api/v1/admin/subscription-tiers/",
        json=payload,
        cookies={"iqbalai_access": "phase1-test-token"},
    )
    _assert_create_succeeds(response, "subscription_tier")


# ── Optional live server (same assertions over HTTP) ──────────────────────────


def _live_backend_reachable() -> bool:
    try:
        response = httpx.get(f"{REAL_BACKEND_URL}/health", timeout=2.0)
        return response.status_code == 200
    except httpx.HTTPError:
        return False


@pytest.mark.real_backend
@pytest.mark.skipif(
    not _live_backend_reachable() or not os.environ.get("TEST_PLATFORM_ADMIN_TOKEN"),
    reason=f"live API not reachable at {REAL_BACKEND_URL} or TEST_PLATFORM_ADMIN_TOKEN unset",
)
def test_live_exam_syllabus_create_accepts_ui_payload() -> None:
    """Same contract check against a running docker/local API process."""
    token = os.environ["TEST_PLATFORM_ADMIN_TOKEN"]
    response = httpx.post(
        f"{REAL_BACKEND_URL}/admin/exam-syllabi",
        json=EXAM_SYLLABUS_CREATE_FROM_UI,
        cookies={"iqbalai_access": token},
        timeout=10.0,
    )
    _assert_create_succeeds(response, "live exam_syllabus")
