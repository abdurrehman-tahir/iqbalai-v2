"""API contract tests for student enrollment — T-077."""

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
from app.features.student_enrollments.models import StudentEnrollment, StudentEnrollmentStatus
from app.features.users.models import User, UserAccountStatus, UserRole


class _FakeEnrollmentRepo:
    store: dict[str, StudentEnrollment] = {}
    by_student_session: dict[tuple[str, str], StudentEnrollment] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def get_by_id(self, enrollment_id: str) -> StudentEnrollment | None:
        return self.store.get(enrollment_id)

    async def get_active_by_student_session(
        self, student_user_id: str, academic_session: str
    ) -> StudentEnrollment | None:
        return self.by_student_session.get((student_user_id, academic_session))

    async def create(self, enrollment: StudentEnrollment) -> StudentEnrollment:
        now = datetime.now(timezone.utc)
        enrollment.created_at = now
        enrollment.updated_at = now
        self.store[enrollment.id] = enrollment
        self.by_student_session[(enrollment.student_user_id, enrollment.academic_session)] = (
            enrollment
        )
        return enrollment


class _FakeUserRepo:
    users: dict[str, User] = {}
    by_email: dict[str, User] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def get_by_authentik_id(self, authentik_id: str) -> User | None:
        return self.users.get(authentik_id)

    async def get_by_email(self, email: str) -> User | None:
        return self.by_email.get(email.lower())

    async def create(self, user: User) -> User:
        now = datetime.now(timezone.utc)
        user.created_at = now
        user.updated_at = now
        self.users[user.id] = user
        self.by_email[user.email.lower()] = user
        return user


class _FakeIndependentUserRepo:
    def __init__(self, session: Any) -> None:
        pass

    async def get_by_email(self, email: str) -> None:
        return None


class _FakeInviteRepo:
    pending: dict[str, Any] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def get_pending_by_email(self, email: str) -> None:
        return self.pending.get(email.lower())

    async def create(self, invite: Any) -> Any:
        return invite


class _FakeSectionRepo:
    store: dict[str, Section] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def get_by_id(self, id: str) -> Section | None:
        return self.store.get(id)

    async def list_by_grade(self, grade_id: str, include_archived: bool = False) -> list[Section]:
        return [s for s in self.store.values() if s.grade_id == grade_id]


class _FakeGradeRepo:
    store: dict[str, Grade] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def get_by_id(self, id: str) -> Grade | None:
        return self.store.get(id)

    async def list_by_school_session(self, *args: Any, **kwargs: Any) -> list[Grade]:
        return list(self.store.values())

    async def get_by_name_session(self, *args: Any, **kwargs: Any) -> Grade | None:
        return None

    async def create(self, grade: Grade) -> Grade:
        self.store[grade.id] = grade
        return grade

    async def update(self, grade: Grade) -> Grade:
        return grade


class _FakeSessionRepo:
    school_active_label: dict[str, str | None] = {"school-1": "2025-2026"}

    def __init__(self, session: Any) -> None:
        pass

    async def get_school_active_label(self, school_id: str) -> str | None:
        return self.school_active_label.get(school_id)

    async def get_active(self, school_id: str) -> Any:
        return None


class _FakeAuthentik:
    async def create_user(self, **kwargs: Any) -> str:
        return "auth-new-student"

    async def add_to_group(self, user_id: str, group: str) -> None:
        return None


def _seed_grade_and_sections() -> None:
    _FakeGradeRepo.store = {
        "grade-9": Grade(
            id="grade-9",
            school_id="school-1",
            name="Grade 9",
            academic_session="2025-2026",
            level_ordinal=9,
            status=GradeStatus.ACTIVE,
        )
    }
    _FakeSectionRepo.store = {
        "section-a": Section(
            id="section-a",
            grade_id="grade-9",
            name="A",
            is_default_internal=False,
            status=SectionStatus.ACTIVE,
        ),
        "default-9": Section(
            id="default-9",
            grade_id="grade-9",
            name=DEFAULT_INTERNAL_NAME,
            is_default_internal=True,
            status=SectionStatus.ACTIVE,
        ),
    }


def _coordinator(scope: str = "Grade 9") -> User:
    return User(
        id="coord-1",
        authentik_id="coord-1",
        email="coord@test.com",
        display_name="Coord",
        role=UserRole.COORDINATOR,
        status=UserAccountStatus.ACTIVE,
        school_id="school-1",
        scoped_ids=scope,
    )


@pytest.fixture(autouse=True)
def _patch_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    _seed_grade_and_sections()
    _FakeEnrollmentRepo.store = {}
    _FakeEnrollmentRepo.by_student_session = {}
    _FakeUserRepo.users = {"coord-1": _coordinator()}
    _FakeUserRepo.by_email = {}
    _FakeInviteRepo.pending = {}

    monkeypatch.setattr(
        "app.features.student_enrollments.service.StudentEnrollmentRepository",
        _FakeEnrollmentRepo,
    )
    monkeypatch.setattr("app.features.student_enrollments.service.UserRepository", _FakeUserRepo)
    monkeypatch.setattr(
        "app.features.student_enrollments.service.IndependentUserRepository",
        _FakeIndependentUserRepo,
    )
    monkeypatch.setattr(
        "app.features.student_enrollments.service.UserInviteRepository", _FakeInviteRepo
    )
    monkeypatch.setattr(
        "app.features.student_enrollments.service.SectionRepository", _FakeSectionRepo
    )
    monkeypatch.setattr("app.features.grades.service.GradeRepository", _FakeGradeRepo)
    monkeypatch.setattr("app.features.grades.service.AcademicSessionRepository", _FakeSessionRepo)
    monkeypatch.setattr("app.features.grades.service.UserRepository", _FakeUserRepo)
    monkeypatch.setattr("app.features.grades.service.SectionRepository", _FakeSectionRepo)
    monkeypatch.setattr(
        "app.features.student_enrollments.service.get_authentik_client", lambda: _FakeAuthentik()
    )
    monkeypatch.setattr("app.features.student_enrollments.service.send_invite_email", AsyncMock())
    monkeypatch.setattr("app.features.student_enrollments.service.audit", AsyncMock())


def _build_client(scope: str = "Grade 9") -> AsyncClient:
    _FakeUserRepo.users["coord-1"] = _coordinator(scope=scope)
    app = FastAPI()
    app.include_router(v1_router, prefix="/api/v1")
    setup_exception_handlers(app)

    async def _override_db() -> AsyncGenerator[None, None]:
        yield None

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = lambda: {
        "sub": "coord-1",
        "role": "coordinator",
        "school_id": "school-1",
        "scoped_ids": scope,
    }
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_enroll_student_into_section() -> None:
    async with _build_client() as client:
        resp = await client.post(
            "/api/v1/grades/grade-9/enrollments/",
            json={
                "display_name": "Ali Khan",
                "email": "ali@school.edu",
                "section_id": "section-a",
            },
        )

    assert resp.status_code == 201
    body = resp.json()["data"]
    assert body["grade_id"] == "grade-9"
    assert body["section_id"] == "section-a"
    assert body["student"]["status"] == "invited"
    assert body["student"]["email"] == "ali@school.edu"


@pytest.mark.asyncio
async def test_enroll_without_section_uses_default_internal() -> None:
    async with _build_client() as client:
        resp = await client.post(
            "/api/v1/grades/grade-9/enrollments/",
            json={"display_name": "Sara", "email": "sara@school.edu"},
        )

    assert resp.status_code == 201
    assert resp.json()["data"]["section_id"] == "default-9"


@pytest.mark.asyncio
async def test_enroll_out_of_scope_forbidden() -> None:
    async with _build_client(scope="Grade 10") as client:
        resp = await client.post(
            "/api/v1/grades/grade-9/enrollments/",
            json={"display_name": "Ali", "email": "ali2@school.edu"},
        )

    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_enroll_duplicate_email_conflict() -> None:
    _FakeUserRepo.by_email["dup@school.edu"] = User(
        id="student-1",
        authentik_id="auth-student-1",
        email="dup@school.edu",
        display_name="Dup",
        role=UserRole.STUDENT,
        status=UserAccountStatus.INVITED,
        school_id="school-1",
    )

    async with _build_client() as client:
        resp = await client.post(
            "/api/v1/grades/grade-9/enrollments/",
            json={"display_name": "Dup", "email": "dup@school.edu"},
        )

    assert resp.status_code == 409
