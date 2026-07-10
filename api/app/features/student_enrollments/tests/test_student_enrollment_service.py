"""Service unit tests for student enrollment — T-077."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from app.core.exceptions import ConflictError, PermissionDeniedError
from app.features.grades.models import Grade, GradeStatus
from app.features.sections.models import DEFAULT_INTERNAL_NAME, Section, SectionStatus
from app.features.student_enrollments.models import StudentEnrollment, StudentEnrollmentStatus
from app.features.student_enrollments.schemas import StudentEnrollmentCreate
from app.features.student_enrollments.service import StudentEnrollmentService
from app.features.users.models import User, UserAccountStatus, UserRole


def _grade() -> Grade:
    return Grade(
        id="grade-9",
        school_id="school-1",
        name="Grade 9",
        academic_session="2025-2026",
        level_ordinal=9,
        status=GradeStatus.ACTIVE,
    )


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


@pytest.fixture
def mock_session() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def svc(mock_session: AsyncMock) -> StudentEnrollmentService:
    service = StudentEnrollmentService(mock_session, authentik=AsyncMock())
    service._authentik.create_user = AsyncMock(return_value="auth-student-1")  # type: ignore[method-assign]
    service._authentik.add_to_group = AsyncMock()  # type: ignore[method-assign]
    service._grade_svc.get_grade = AsyncMock(return_value=_grade())  # type: ignore[method-assign]
    service._grade_svc._load_actor = AsyncMock(return_value=_coordinator())  # type: ignore[method-assign]
    service._ensure_email_available = AsyncMock()  # type: ignore[method-assign]
    service._invites.create = AsyncMock()  # type: ignore[method-assign]
    service._repo.get_active_by_student_session = AsyncMock(return_value=None)  # type: ignore[method-assign]
    service._repo.create = AsyncMock(side_effect=lambda row: row)  # type: ignore[method-assign]
    service._users.create = AsyncMock(side_effect=lambda user: user)  # type: ignore[method-assign]
    return service


@pytest.mark.asyncio
async def test_enroll_uses_named_section(svc: StudentEnrollmentService) -> None:
    section = Section(
        id="section-a",
        grade_id="grade-9",
        name="A",
        is_default_internal=False,
        status=SectionStatus.ACTIVE,
    )
    svc._resolve_section = AsyncMock(return_value=section)  # type: ignore[method-assign]

    enrollment, student = await svc.enroll_student(
        "grade-9",
        StudentEnrollmentCreate(
            display_name="Ali Khan",
            email="ali@school.edu",
            section_id="section-a",
        ),
        {"sub": "coord-1", "school_id": "school-1", "role": "coordinator"},
        actor_id="coord-1",
    )

    assert enrollment.section_id == "section-a"
    assert enrollment.academic_session == "2025-2026"
    assert student.status == UserAccountStatus.INVITED
    assert student.role == UserRole.STUDENT


@pytest.mark.asyncio
async def test_enroll_defaults_to_internal_section(svc: StudentEnrollmentService) -> None:
    default = Section(
        id="default-9",
        grade_id="grade-9",
        name=DEFAULT_INTERNAL_NAME,
        is_default_internal=True,
        status=SectionStatus.ACTIVE,
    )
    svc._resolve_section = AsyncMock(return_value=default)  # type: ignore[method-assign]

    enrollment, _student = await svc.enroll_student(
        "grade-9",
        StudentEnrollmentCreate(display_name="Sara", email="sara@school.edu"),
        {"sub": "coord-1", "school_id": "school-1", "role": "coordinator"},
        actor_id="coord-1",
    )

    assert enrollment.section_id == "default-9"


@pytest.mark.asyncio
async def test_enroll_out_of_scope_raises(svc: StudentEnrollmentService) -> None:
    svc._grade_svc._load_actor = AsyncMock(return_value=_coordinator(scope="Grade 10"))  # type: ignore[method-assign]

    with pytest.raises(PermissionDeniedError):
        await svc.enroll_student(
            "grade-9",
            StudentEnrollmentCreate(display_name="Ali", email="ali@school.edu"),
            {"sub": "coord-1", "school_id": "school-1", "role": "coordinator"},
            actor_id="coord-1",
        )


@pytest.mark.asyncio
async def test_enroll_duplicate_active_session_raises(svc: StudentEnrollmentService) -> None:
    svc._resolve_section = AsyncMock(  # type: ignore[method-assign]
        return_value=Section(
            id="section-a",
            grade_id="grade-9",
            name="A",
            is_default_internal=False,
            status=SectionStatus.ACTIVE,
        )
    )
    svc._repo.get_active_by_student_session = AsyncMock(  # type: ignore[method-assign]
        return_value=StudentEnrollment(
            id="existing",
            school_id="school-1",
            student_user_id="student-1",
            grade_id="grade-9",
            section_id="section-a",
            academic_session="2025-2026",
            status=StudentEnrollmentStatus.ACTIVE,
            enrolled_at=datetime.now(timezone.utc),
        )
    )

    with pytest.raises(ConflictError, match="active enrollment"):
        await svc.enroll_student(
            "grade-9",
            StudentEnrollmentCreate(display_name="Ali", email="ali@school.edu"),
            {"sub": "coord-1", "school_id": "school-1", "role": "coordinator"},
            actor_id="coord-1",
        )
