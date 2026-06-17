"""API contract tests for Grade endpoints — T-043."""

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
from app.features.grades.models import Grade, GradeStatus
from app.features.users.models import User, UserAccountStatus, UserRole


class _FakeGradeRepo:
    store: dict[str, Grade] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def list_by_school_session(
        self, school_id: str, academic_session: str, include_archived: bool = False
    ) -> list[Grade]:
        rows = [
            g
            for g in self.store.values()
            if g.school_id == school_id
            and g.academic_session == academic_session
            and g.deleted_at is None
        ]
        if not include_archived:
            rows = [g for g in rows if g.status == GradeStatus.ACTIVE]
        return sorted(rows, key=lambda g: g.level_ordinal)

    async def get_by_id(self, id: str) -> Grade | None:
        return self.store.get(id)

    async def get_by_name_session(
        self, school_id: str, name: str, academic_session: str
    ) -> Grade | None:
        return next(
            (
                g
                for g in self.store.values()
                if g.school_id == school_id
                and g.name == name
                and g.academic_session == academic_session
                and g.deleted_at is None
            ),
            None,
        )

    async def create(self, grade: Grade) -> Grade:
        now = datetime.now(timezone.utc)
        grade.created_at = now
        grade.updated_at = now
        self.store[grade.id] = grade
        return grade

    async def update(self, grade: Grade) -> Grade:
        self.store[grade.id] = grade
        return grade


class _FakeSessionRepo:
    school_active_label: dict[str, str | None] = {"school-1": "2025-2026"}

    def __init__(self, session: Any) -> None:
        pass

    async def get_school_active_label(self, school_id: str) -> str | None:
        return self.school_active_label.get(school_id)

    async def get_active(self, school_id: str) -> Any:
        return None


class _FakeUserRepo:
    users: dict[str, User] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def get_by_authentik_id(self, authentik_id: str) -> User | None:
        return self.users.get(authentik_id)


def _coordinator(scope: str = "Grade 9,Grade 10") -> User:
    return User(
        id="user-1",
        authentik_id="user-1",
        email="coord@test.com",
        display_name="Coord",
        role=UserRole.COORDINATOR,
        status=UserAccountStatus.ACTIVE,
        school_id="school-1",
        scoped_ids=scope,
    )


@pytest.fixture(autouse=True)
def _patch_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    _FakeGradeRepo.store = {}
    _FakeSessionRepo.school_active_label = {"school-1": "2025-2026", "school-2": "2025-2026"}
    _FakeUserRepo.users = {"user-1": _coordinator()}
    monkeypatch.setattr("app.features.grades.service.GradeRepository", _FakeGradeRepo)
    monkeypatch.setattr("app.features.grades.service.AcademicSessionRepository", _FakeSessionRepo)
    monkeypatch.setattr("app.features.grades.service.UserRepository", _FakeUserRepo)
    monkeypatch.setattr("app.features.grades.service.audit", AsyncMock())


def _build_client(role: str = "coordinator", school_id: str = "school-1") -> AsyncClient:
    app = FastAPI()
    app.include_router(v1_router, prefix="/api/v1")
    setup_exception_handlers(app)

    async def _fake_db() -> AsyncGenerator[Any, None]:
        yield AsyncMock()

    def _claims() -> dict[str, object]:
        return {"sub": "user-1", "role": role, "school_id": school_id}

    app.dependency_overrides[get_db] = _fake_db
    app.dependency_overrides[get_current_user] = _claims
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


async def test_create_grade_pinned_to_active_session() -> None:
    async with _build_client() as client:
        resp = await client.post("/api/v1/grades/", json={"name": "Grade 9"})
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["name"] == "Grade 9"
    assert data["academic_session"] == "2025-2026"
    assert data["level_ordinal"] == 9
    assert data["promoted_from_grade_id"] is None


async def test_duplicate_name_same_session_returns_409() -> None:
    async with _build_client() as client:
        first = await client.post("/api/v1/grades/", json={"name": "Grade 9"})
        assert first.status_code == 201
        dup = await client.post("/api/v1/grades/", json={"name": "Grade 9"})
    assert dup.status_code == 409


async def test_same_name_different_session_allowed() -> None:
    async with _build_client() as client:
        r1 = await client.post("/api/v1/grades/", json={"name": "Grade 9"})
        assert r1.status_code == 201
    _FakeSessionRepo.school_active_label["school-1"] = "2026-2027"
    async with _build_client() as client:
        r2 = await client.post("/api/v1/grades/", json={"name": "Grade 9"})
    assert r2.status_code == 201


async def test_out_of_scope_grade_forbidden() -> None:
    _FakeUserRepo.users["user-1"] = _coordinator("Grade 11,Grade 12")
    async with _build_client() as client:
        resp = await client.post("/api/v1/grades/", json={"name": "Grade 9"})
    assert resp.status_code == 403


async def test_archive_grade() -> None:
    async with _build_client() as client:
        created = await client.post("/api/v1/grades/", json={"name": "Grade 9"})
        grade_id = created.json()["data"]["id"]
        archived = await client.post(f"/api/v1/grades/{grade_id}/archive")
    assert archived.status_code == 200
    assert archived.json()["data"]["status"] == "archived"


async def test_list_filters_by_coordinator_scope() -> None:
    now = datetime.now(timezone.utc)
    for name, level in [("Grade 9", 9), ("Grade 10", 10), ("Grade 11", 11)]:
        g = Grade(
            id=f"g-{level}",
            school_id="school-1",
            name=name,
            academic_session="2025-2026",
            level_ordinal=level,
            status=GradeStatus.ACTIVE,
        )
        g.created_at = now
        g.updated_at = now
        _FakeGradeRepo.store[g.id] = g
    _FakeUserRepo.users["user-1"] = _coordinator("Grade 9,Grade 10")
    async with _build_client() as client:
        resp = await client.get("/api/v1/grades/")
    names = [g["name"] for g in resp.json()["data"]]
    assert "Grade 9" in names
    assert "Grade 10" in names
    assert "Grade 11" not in names
