"""API contract tests for the District endpoints — T-029.

These exercise the router through the real FastAPI stack (routing, ``require_role``,
the response envelope, status codes, and the Idempotency-Key dependency) using a
bare app without ``AuthMiddleware`` — auth claims are injected via
``dependency_overrides`` so we can drive the role check directly. The DB is replaced
by a fake repository so no Postgres is needed, and the audit writer is a no-op.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.v1.router import router as v1_router
from app.core.dependencies import get_current_user, get_db
from app.core.exceptions import setup_exception_handlers
from app.features.schools.models import District


class _FakeRepo:
    """In-memory stand-in for DistrictRepository, sharing one store per test."""

    store: dict[str, District] = {}

    def __init__(self, session: Any) -> None:  # session unused
        pass

    async def list_districts(self) -> list[District]:
        return [d for d in self.store.values() if d.deleted_at is None]

    async def get_by_id(self, id: str) -> District | None:
        return self.store.get(id)

    async def get_active_by_name(self, name: str) -> District | None:
        return next(
            (d for d in self.store.values() if d.name == name and d.deleted_at is None),
            None,
        )

    async def create(self, district: District) -> District:
        # The real Postgres AuditMixin defaults stamp these server-side; mimic that
        # here so DistrictRead (which requires created_at) validates.
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        district.created_at = now
        district.updated_at = now
        self.store[district.id] = district
        return district

    async def update(self, district: District) -> District:
        self.store[district.id] = district
        return district

    async def soft_delete(self, district: District) -> None:
        from datetime import datetime, timezone

        district.deleted_at = datetime.now(timezone.utc)


@pytest.fixture(autouse=True)
def _patch_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    """Swap the repo for the in-memory fake, no-op the audit writer, fake Redis."""
    _FakeRepo.store = {}
    monkeypatch.setattr("app.features.schools.service.DistrictRepository", _FakeRepo)
    monkeypatch.setattr("app.features.schools.service.audit", AsyncMock(return_value=None))


def _build_client(role: str = "platform_admin") -> AsyncClient:
    app = FastAPI()
    app.include_router(v1_router, prefix="/api/v1")
    setup_exception_handlers(app)

    async def _fake_db() -> AsyncGenerator[Any, None]:
        yield AsyncMock()

    def _claims() -> dict[str, object]:
        return {"sub": "admin-1", "role": role, "tenant_id": "t1"}

    app.dependency_overrides[get_db] = _fake_db
    app.dependency_overrides[get_current_user] = _claims
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


async def test_create_district_returns_201_envelope() -> None:
    async with _build_client() as client:
        resp = await client.post(
            "/api/v1/admin/districts/",
            json={"name": "Karachi District", "region": "Sindh", "language_preference": "en"},
        )
    assert resp.status_code == 201
    body = resp.json()
    assert body["message"] == "ok"
    assert body["data"]["name"] == "Karachi District"
    assert body["data"]["region"] == "Sindh"
    assert len(body["data"]["id"]) == 36


async def test_list_districts_returns_created() -> None:
    async with _build_client() as client:
        await client.post("/api/v1/admin/districts/", json={"name": "Lahore District"})
        resp = await client.get("/api/v1/admin/districts/")
    assert resp.status_code == 200
    names = [d["name"] for d in resp.json()["data"]]
    assert "Lahore District" in names


async def test_create_duplicate_name_returns_409() -> None:
    async with _build_client() as client:
        await client.post("/api/v1/admin/districts/", json={"name": "Dup District"})
        resp = await client.post("/api/v1/admin/districts/", json={"name": "Dup District"})
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "CONFLICT"


async def test_non_admin_is_forbidden() -> None:
    async with _build_client(role="teacher") as client:
        resp = await client.post("/api/v1/admin/districts/", json={"name": "Nope District"})
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "PERMISSION_DENIED"


async def test_idempotent_replay_returns_same_district(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Same Idempotency-Key + same body returns the cached response, not a new row."""
    from app.core.tests.test_idempotency import FakeRedis

    redis = FakeRedis()
    monkeypatch.setattr("app.core.idempotency.get_redis", lambda: redis)

    async with _build_client() as client:
        headers = {"Idempotency-Key": "key-123"}
        first = await client.post(
            "/api/v1/admin/districts/", json={"name": "Idem District"}, headers=headers
        )
        second = await client.post(
            "/api/v1/admin/districts/", json={"name": "Idem District"}, headers=headers
        )
    assert first.status_code == 201
    assert second.json()["data"]["id"] == first.json()["data"]["id"]
    # Only one district actually created.
    assert len(_FakeRepo.store) == 1


async def test_idempotency_key_mismatch_returns_409(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Same key with a different body is a 409 IDEMPOTENCY_KEY_MISMATCH."""
    from app.core.tests.test_idempotency import FakeRedis

    redis = FakeRedis()
    monkeypatch.setattr("app.core.idempotency.get_redis", lambda: redis)

    async with _build_client() as client:
        headers = {"Idempotency-Key": "key-xyz"}
        await client.post(
            "/api/v1/admin/districts/", json={"name": "First District"}, headers=headers
        )
        resp = await client.post(
            "/api/v1/admin/districts/", json={"name": "Different District"}, headers=headers
        )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "IDEMPOTENCY_KEY_MISMATCH"
