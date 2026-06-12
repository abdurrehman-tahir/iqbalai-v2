"""API contract tests for school admin endpoints — T-032."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.v1.router import router as v1_router
from app.core.dependencies import get_current_user, get_db
from app.core.exceptions import setup_exception_handlers
from app.features.schools.models import District, School


class _FakeSchoolRepo:
    schools: dict[str, School] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def get_by_id(self, id: str) -> School | None:
        return self.schools.get(id)

    async def list_by_district(self, district_id: str) -> list[School]:
        return [s for s in self.schools.values() if s.district_id == district_id]


class _FakeDistrictRepo:
    districts: dict[str, District] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def get_by_id(self, id: str) -> District | None:
        return self.districts.get(id)


@pytest.fixture(autouse=True)
def _patch_repos(monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime.now(timezone.utc)
    _FakeSchoolRepo.schools = {
        "school-1": School(
            id="school-1",
            district_id="dist-1",
            name="My School",
            created_at=now,
            updated_at=now,
        ),
        "school-2": School(
            id="school-2",
            district_id="dist-1",
            name="Other School",
            created_at=now,
            updated_at=now,
        ),
    }
    _FakeDistrictRepo.districts = {
        "dist-1": District(id="dist-1", name="District 1", region="Punjab")
    }
    monkeypatch.setattr("app.features.schools.service.SchoolRepository", _FakeSchoolRepo)
    monkeypatch.setattr("app.features.schools.service.DistrictRepository", _FakeDistrictRepo)


def _build_client(
    role: str = "school_admin",
    school_id: str | None = "school-1",
    district_id: str | None = "dist-1",
) -> AsyncClient:
    app = FastAPI()
    app.include_router(v1_router, prefix="/api/v1")
    setup_exception_handlers(app)

    async def _fake_db() -> AsyncGenerator[Any, None]:
        yield AsyncMock()

    def _claims() -> dict[str, object]:
        data: dict[str, object] = {"sub": "sa-1", "role": role}
        if school_id is not None:
            data["school_id"] = school_id
        if district_id is not None:
            data["district_id"] = district_id
        return data

    app.dependency_overrides[get_db] = _fake_db
    app.dependency_overrides[get_current_user] = _claims
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


async def test_school_admin_get_my_school() -> None:
    async with _build_client() as client:
        resp = await client.get("/api/v1/school/admin/school")
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["id"] == "school-1"
    assert body["data"]["name"] == "My School"


async def test_school_admin_cross_school_get_returns_404() -> None:
    async with _build_client() as client:
        resp = await client.get("/api/v1/school/admin/schools/school-2")
    assert resp.status_code == 404


async def test_school_admin_get_own_school_by_id() -> None:
    async with _build_client() as client:
        resp = await client.get("/api/v1/school/admin/schools/school-1")
    assert resp.status_code == 200
    assert resp.json()["data"]["name"] == "My School"
