"""API contract tests for Section endpoints — T-044."""

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
from app.features.sections.models import DEFAULT_INTERNAL_NAME, Section, SectionStatus
from app.features.users.models import User, UserAccountStatus, UserRole


class _FakeSectionRepo:
    store: dict[str, Section] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def list_by_grade(self, grade_id: str, include_archived: bool = False) -> list[Section]:
        rows = [s for s in self.store.values() if s.grade_id == grade_id and s.deleted_at is None]
        if not include_archived:
            rows = [s for s in rows if s.status == SectionStatus.ACTIVE]
        return rows

    async def list_visible_by_grade(self, grade_id: str) -> list[Section]:
        rows = await self.list_by_grade(grade_id)
        return [s for s in rows if not s.is_default_internal]

    async def get_by_id(self, id: str) -> Section | None:
        return self.store.get(id)

    async def get_by_name(self, grade_id: str, name: str) -> Section | None:
        return next(
            (
                s
                for s in self.store.values()
                if s.grade_id == grade_id and s.name == name and s.deleted_at is None
            ),
            None,
        )

    async def count_default_internal(self, grade_id: str) -> int:
        return sum(
            1 for s in self.store.values() if s.grade_id == grade_id and s.is_default_internal
        )

    async def create(self, section: Section) -> Section:
        now = datetime.now(timezone.utc)
        section.created_at = now
        section.updated_at = now
        self.store[section.id] = section
        return section

    async def update(self, section: Section) -> Section:
        self.store[section.id] = section
        return section

    async def archive_all_for_grade(self, grade_id: str) -> None:
        for s in self.store.values():
            if s.grade_id == grade_id:
                s.status = SectionStatus.ARCHIVED

    async def create_default_internal(self, grade_id: str) -> Section:
        section = Section(
            id=f"default-{grade_id}",
            grade_id=grade_id,
            name=DEFAULT_INTERNAL_NAME,
            is_default_internal=True,
            status=SectionStatus.ACTIVE,
        )
        return await self.create(section)


class _FakeGradeRepo:
    store: dict[str, Grade] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def list_by_school_session(
        self, school_id: str, academic_session: str, include_archived: bool = False
    ) -> list[Grade]:
        return list(self.store.values())

    async def get_by_id(self, id: str) -> Grade | None:
        return self.store.get(id)

    async def get_by_name_session(
        self, school_id: str, name: str, academic_session: str
    ) -> Grade | None:
        return None

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
    def __init__(self, session: Any) -> None:
        pass

    async def get_school_active_label(self, school_id: str) -> str | None:
        return "2025-2026"

    async def get_active(self, school_id: str) -> Any:
        return None


class _FakeUserRepo:
    users: dict[str, User] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def get_by_id(self, user_id: str) -> User | None:
        return self.users.get(user_id)

    async def get_by_authentik_id(self, authentik_id: str) -> User | None:
        # In these unit tests, we store users keyed by the same value
        # used by `claims.sub`.
        return self.users.get(authentik_id)


@pytest.fixture(autouse=True)
def _patch_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    _FakeSectionRepo.store = {}
    _FakeGradeRepo.store = {}
    grade = Grade(
        id="grade-9",
        school_id="school-1",
        name="Grade 9",
        academic_session="2025-2026",
        level_ordinal=9,
        status=GradeStatus.ACTIVE,
    )
    grade.created_at = datetime.now(timezone.utc)
    grade.updated_at = grade.created_at
    _FakeGradeRepo.store[grade.id] = grade
    _FakeUserRepo.users = {
        "user-1": User(
            id="user-1",
            authentik_id="user-1",
            email="c@test.com",
            display_name="C",
            role=UserRole.COORDINATOR,
            status=UserAccountStatus.ACTIVE,
            school_id="school-1",
            scoped_ids="Grade 9,Grade 10",
        )
    }
    monkeypatch.setattr("app.features.sections.service.SectionRepository", _FakeSectionRepo)
    monkeypatch.setattr("app.features.grades.service.GradeRepository", _FakeGradeRepo)
    monkeypatch.setattr("app.features.grades.service.AcademicSessionRepository", _FakeSessionRepo)
    monkeypatch.setattr("app.features.grades.service.UserRepository", _FakeUserRepo)
    monkeypatch.setattr("app.features.grades.service.SectionRepository", _FakeSectionRepo)
    monkeypatch.setattr("app.features.sections.service.audit", AsyncMock())
    monkeypatch.setattr("app.features.grades.service.audit", AsyncMock())


def _build_client() -> AsyncClient:
    app = FastAPI()
    app.include_router(v1_router, prefix="/api/v1")
    setup_exception_handlers(app)

    async def _fake_db() -> AsyncGenerator[Any, None]:
        yield AsyncMock()

    def _claims() -> dict[str, object]:
        return {"sub": "user-1", "role": "coordinator", "school_id": "school-1"}

    app.dependency_overrides[get_db] = _fake_db
    app.dependency_overrides[get_current_user] = _claims
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def test_grade_create_auto_creates_default_internal() -> None:
    _FakeGradeRepo.store = {}
    _FakeSectionRepo.store = {}
    async with _build_client() as client:
        resp = await client.post("/api/v1/grades/", json={"name": "Grade 9"})
    assert resp.status_code == 201
    grade_id = resp.json()["data"]["id"]
    count = sum(
        1
        for s in _FakeSectionRepo.store.values()
        if s.grade_id == grade_id and s.is_default_internal
    )
    assert count == 1


async def test_create_visible_sections() -> None:
    async with _build_client() as client:
        a = await client.post("/api/v1/grades/grade-9/sections/", json={"name": "A"})
        b = await client.post("/api/v1/grades/grade-9/sections/", json={"name": "B"})
        listing = await client.get("/api/v1/grades/grade-9/sections/")
    assert a.status_code == 201
    assert b.status_code == 201
    names = [s["name"] for s in listing.json()["data"]]
    assert names == ["A", "B"]
    assert DEFAULT_INTERNAL_NAME not in names


async def test_duplicate_section_name_rejected() -> None:
    async with _build_client() as client:
        await client.post("/api/v1/grades/grade-9/sections/", json={"name": "A"})
        dup = await client.post("/api/v1/grades/grade-9/sections/", json={"name": "A"})
    assert dup.status_code == 409


async def test_archive_grade_cascades_sections() -> None:
    async with _build_client() as client:
        await client.post("/api/v1/grades/grade-9/sections/", json={"name": "A"})
        await client.post("/api/v1/grades/grade-9/archive")
    for s in _FakeSectionRepo.store.values():
        assert s.status == SectionStatus.ARCHIVED
