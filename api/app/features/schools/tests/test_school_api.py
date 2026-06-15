"""API contract tests for School endpoints — T-031."""

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
    store: dict[str, School] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def list_schools(self, district_id: str | None = None) -> list[School]:
        schools = [s for s in self.store.values() if s.deleted_at is None]
        if district_id is not None:
            schools = [s for s in schools if s.district_id == district_id]
        return schools

    async def get_by_id(self, id: str) -> School | None:
        return self.store.get(id)

    async def get_active_by_name_in_district(self, district_id: str, name: str) -> School | None:
        return next(
            (
                s
                for s in self.store.values()
                if s.district_id == district_id and s.name == name and s.deleted_at is None
            ),
            None,
        )

    async def create(self, school: School) -> School:
        now = datetime.now(timezone.utc)
        school.created_at = now
        school.updated_at = now
        self.store[school.id] = school
        return school

    async def update(self, school: School) -> School:
        self.store[school.id] = school
        return school

    async def soft_delete(self, school: School) -> None:
        school.deleted_at = datetime.now(timezone.utc)


class _FakeDistrictRepo:
    districts: dict[str, District] = {"dist-1": District(id="dist-1", name="Punjab")}

    def __init__(self, session: Any) -> None:
        pass

    async def get_by_id(self, id: str) -> District | None:
        return self.districts.get(id)


@pytest.fixture(autouse=True)
def _patch_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    _FakeSchoolRepo.store = {}
    monkeypatch.setattr("app.features.schools.service.SchoolRepository", _FakeSchoolRepo)
    monkeypatch.setattr("app.features.schools.service.DistrictRepository", _FakeDistrictRepo)
    monkeypatch.setattr("app.features.schools.service.audit", AsyncMock())


def _build_client(role: str = "district_admin", district_id: str = "dist-1") -> AsyncClient:
    app = FastAPI()
    app.include_router(v1_router, prefix="/api/v1")
    setup_exception_handlers(app)

    async def _fake_db() -> AsyncGenerator[Any, None]:
        yield AsyncMock()

    def _claims() -> dict[str, object]:
        return {"sub": "user-1", "role": role, "district_id": district_id}

    app.dependency_overrides[get_db] = _fake_db
    app.dependency_overrides[get_current_user] = _claims
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


async def test_create_school_returns_201() -> None:
    async with _build_client() as client:
        resp = await client.post(
            "/api/v1/admin/schools/",
            json={"name": "Sample School", "district_id": "dist-1"},
        )
    assert resp.status_code == 201
    body = resp.json()
    assert body["data"]["name"] == "Sample School"
    assert body["data"]["district_id"] == "dist-1"


async def test_cross_district_get_returns_404() -> None:
    school = School(id="school-x", district_id="dist-other", name="Other School")
    _FakeSchoolRepo.store["school-x"] = school

    async with _build_client(district_id="dist-1") as client:
        resp = await client.get("/api/v1/admin/schools/school-x")
    assert resp.status_code == 404


async def test_platform_admin_can_get_any_school() -> None:
    now = datetime.now(timezone.utc)
    school = School(id="school-x", district_id="dist-other", name="Other School")
    school.created_at = now
    school.updated_at = now
    _FakeSchoolRepo.store["school-x"] = school

    async with _build_client(role="platform_admin", district_id="") as client:
        resp = await client.get("/api/v1/admin/schools/school-x")
    assert resp.status_code == 200
    assert resp.json()["data"]["name"] == "Other School"


async def test_teacher_forbidden() -> None:
    async with _build_client(role="teacher") as client:
        resp = await client.post(
            "/api/v1/admin/schools/",
            json={"name": "Nope", "district_id": "dist-1"},
        )
    assert resp.status_code == 403
