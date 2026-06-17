"""Integration sweep — M-03 structure endpoints enforce coordinator scope (T-048)."""

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
from app.features.subjects.models import Subject, SubjectStatus
from app.features.users.models import User, UserAccountStatus, UserRole


class _FakeGradeRepo:
    store: dict[str, Grade] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def list_by_school_session(self, school_id: str, academic_session: str, include_archived: bool = False) -> list[Grade]:
        return list(self.store.values())

    async def get_by_id(self, id: str) -> Grade | None:
        return self.store.get(id)

    async def get_by_name_session(self, school_id: str, name: str, academic_session: str) -> Grade | None:
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


class _FakeSubjectRepo:
    store: dict[str, Subject] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def list_by_school(self, school_id: str, include_archived: bool = False) -> list[Subject]:
        return list(self.store.values())

    async def get_by_id(self, id: str) -> Subject | None:
        return self.store.get(id)

    async def get_active_by_name(self, school_id: str, name: str) -> Subject | None:
        return None

    async def create(self, subject: Subject) -> Subject:
        self.store[subject.id] = subject
        return subject

    async def update(self, subject: Subject) -> Subject:
        self.store[subject.id] = subject
        return subject

    async def soft_delete(self, subject: Subject) -> None:
        pass


class _FakeOfferingRepo:
    def __init__(self, session: Any) -> None:
        pass

    async def list_by_grade(self, grade_id: str, include_archived: bool = False) -> list:
        return []

    async def get_by_id(self, id: str):
        return None

    async def get_by_grade_subject(self, grade_id: str, subject_id: str):
        return None

    async def count_active_by_subject(self, subject_id: str) -> int:
        return 0

    async def count_active_assignments_for_teacher(self, teacher_id: str) -> int:
        return 0

    async def create(self, offering):
        return offering

    async def update(self, offering):
        return offering

    async def archive_all_for_grade(self, grade_id: str) -> None:
        pass


class _FakeSectionRepo:
    def __init__(self, session: Any) -> None:
        pass

    async def list_visible_by_grade(self, grade_id: str) -> list:
        return []

    async def get_by_id(self, id: str):
        return None

    async def get_by_name(self, grade_id: str, name: str):
        return None

    async def create(self, section):
        return section

    async def update(self, section):
        return section

    async def archive_all_for_grade(self, grade_id: str) -> None:
        pass

    async def create_default_internal(self, grade_id: str):
        return None


class _FakeSessionRepo:
    def __init__(self, session: Any) -> None:
        pass

    async def get_school_active_label(self, school_id: str) -> str | None:
        return "2025-2026"

    async def get_active(self, school_id: str):
        return None

    async def list_by_school(self, school_id: str) -> list:
        return []

    async def create(self, row):
        return row

    async def activate(self, school_id: str, session_id: str):
        return None


class _FakeUserRepo:
    users: dict[str, User] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def get_by_id(self, user_id: str) -> User | None:
        return self.users.get(user_id)

    async def get_by_authentik_id(self, authentik_id: str) -> User | None:
        for user in self.users.values():
            if user.authentik_id == authentik_id:
                return user
        return self.users.get(authentik_id)

    async def list_by_school_and_role(self, school_id: str, role: UserRole) -> list[User]:
        return []


@pytest.fixture(autouse=True)
def _patch_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime.now(timezone.utc)
    _FakeGradeRepo.store = {
        "grade-11": Grade(
            id="grade-11",
            school_id="school-1",
            name="Grade 11",
            academic_session="2025-2026",
            level_ordinal=11,
            status=GradeStatus.ACTIVE,
        )
    }
    for g in _FakeGradeRepo.store.values():
        g.created_at = now
        g.updated_at = now

    _FakeSubjectRepo.store = {
        "sub-1": Subject(
            id="sub-1",
            school_id="school-1",
            name="Physics",
            language="en",
            status=SubjectStatus.ACTIVE,
        )
    }
    for s in _FakeSubjectRepo.store.values():
        s.created_at = now
        s.updated_at = now

    coord = User(
        id="coord-internal-id",
        authentik_id="coord-1",
        email="c@test.com",
        display_name="C",
        role=UserRole.COORDINATOR,
        status=UserAccountStatus.ACTIVE,
        school_id="school-1",
        scoped_ids="Grade 9,Grade 10",
    )
    coord.created_at = now
    coord.updated_at = now
    _FakeUserRepo.users = {"coord-1": coord}

    for target, path in [
        ("app.features.grades.service.GradeRepository", _FakeGradeRepo),
        ("app.features.grades.service.AcademicSessionRepository", _FakeSessionRepo),
        ("app.features.grades.service.UserRepository", _FakeUserRepo),
        ("app.features.grades.service.SectionRepository", _FakeSectionRepo),
        ("app.features.grades.service.OfferingRepository", _FakeOfferingRepo),
        ("app.features.subjects.service.SubjectRepository", _FakeSubjectRepo),
        ("app.features.subjects.service.OfferingRepository", _FakeOfferingRepo),
        ("app.features.sections.service.SectionRepository", _FakeSectionRepo),
        ("app.features.offerings.service.OfferingRepository", _FakeOfferingRepo),
        ("app.features.offerings.service.SubjectRepository", _FakeSubjectRepo),
        ("app.features.offerings.service.UserRepository", _FakeUserRepo),
        ("app.features.academic_sessions.service.AcademicSessionRepository", _FakeSessionRepo),
        ("app.features.grades.service.GradeRepository", _FakeGradeRepo),
        ("app.features.grades.service.AcademicSessionRepository", _FakeSessionRepo),
        ("app.features.grades.service.UserRepository", _FakeUserRepo),
        ("app.features.grades.service.SectionRepository", _FakeSectionRepo),
        ("app.features.grades.service.OfferingRepository", _FakeOfferingRepo),
    ]:
        monkeypatch.setattr(target, path)

    for svc in (
        "app.features.grades.service",
        "app.features.subjects.service",
        "app.features.sections.service",
        "app.features.offerings.service",
        "app.features.academic_sessions.service",
    ):
        monkeypatch.setattr(f"{svc}.audit", AsyncMock())


def _client() -> AsyncClient:
    app = FastAPI()
    app.include_router(v1_router, prefix="/api/v1")
    setup_exception_handlers(app)

    async def _fake_db() -> AsyncGenerator[Any, None]:
        yield AsyncMock()

    def _claims() -> dict[str, object]:
        return {"sub": "coord-1", "role": "coordinator", "school_id": "school-1"}

    app.dependency_overrides[get_db] = _fake_db
    app.dependency_overrides[get_current_user] = _claims
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.parametrize(
    "method,path,json_body",
    [
        ("GET", "/api/v1/grades/grade-11", None),
        ("POST", "/api/v1/grades/", {"name": "Grade 11"}),
        ("POST", "/api/v1/grades/grade-11/archive", None),
        ("GET", "/api/v1/grades/grade-11/sections/", None),
        ("POST", "/api/v1/grades/grade-11/sections/", {"name": "A"}),
        ("GET", "/api/v1/grades/grade-11/offerings/", None),
        ("POST", "/api/v1/grades/grade-11/offerings/", {"subject_id": "sub-1"}),
    ],
)
async def test_out_of_scope_coordinator_forbidden(method: str, path: str, json_body: dict | None) -> None:
    async with _client() as client:
        if method == "GET":
            resp = await client.get(path)
        elif json_body is None:
            resp = await client.post(path)
        else:
            resp = await client.post(path, json=json_body)
    assert resp.status_code == 403
