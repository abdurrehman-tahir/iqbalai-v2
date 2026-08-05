"""Per-lecture access control API + service tests — T-123, #21."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.v1.router import router as v1_router
from app.core.dependencies import get_current_user, get_db
from app.core.exceptions import setup_exception_handlers
from app.features.lectures.models import (
    LectureAssignmentScope,
    LectureStatus,
    SchoolLecture,
    SchoolLectureAssignment,
)
from app.features.lectures.service import LectureWizardService
from app.features.offerings.models import GradeSubjectOffering, OfferingStatus
from app.features.sections.models import Section, SectionStatus
from app.features.student_enrollments.models import StudentEnrollment, StudentEnrollmentStatus
from app.features.users.models import User, UserAccountStatus, UserRole

TEACHER = User(
    id="teacher-1",
    authentik_id="auth-teacher",
    email="teacher@example.com",
    display_name="Teacher One",
    role=UserRole.TEACHER,
    status=UserAccountStatus.ACTIVE,
    school_id="school-1",
)
OTHER_TEACHER = User(
    id="teacher-2",
    authentik_id="auth-teacher-2",
    email="teacher2@example.com",
    display_name="Teacher Two",
    role=UserRole.TEACHER,
    status=UserAccountStatus.ACTIVE,
    school_id="school-1",
)
COORDINATOR = User(
    id="coord-1",
    authentik_id="auth-coord",
    email="coord@example.com",
    display_name="Coordinator One",
    role=UserRole.COORDINATOR,
    status=UserAccountStatus.ACTIVE,
    school_id="school-1",
)
OTHER_SCHOOL_ADMIN = User(
    id="admin-2",
    authentik_id="auth-admin-2",
    email="admin2@example.com",
    display_name="Admin at Other School",
    role=UserRole.SCHOOL_ADMIN,
    status=UserAccountStatus.ACTIVE,
    school_id="school-2",
)
STUDENT_1 = User(
    id="student-1",
    authentik_id="auth-student-1",
    email="student1@example.com",
    display_name="Student One",
    role=UserRole.STUDENT,
    status=UserAccountStatus.ACTIVE,
    school_id="school-1",
)
STUDENT_2 = User(
    id="student-2",
    authentik_id="auth-student-2",
    email="student2@example.com",
    display_name="Student Two",
    role=UserRole.STUDENT,
    status=UserAccountStatus.ACTIVE,
    school_id="school-1",
)
STUDENT_OTHER_GRADE = User(
    id="student-3",
    authentik_id="auth-student-3",
    email="student3@example.com",
    display_name="Student Three",
    role=UserRole.STUDENT,
    status=UserAccountStatus.ACTIVE,
    school_id="school-1",
)
STUDENT_UNENROLLED = User(
    id="student-4",
    authentik_id="auth-student-4",
    email="student4@example.com",
    display_name="Student Four",
    role=UserRole.STUDENT,
    status=UserAccountStatus.ACTIVE,
    school_id="school-1",
)

SECTION_A = Section(id="section-a", grade_id="grade-9", name="A", status=SectionStatus.ACTIVE)
SECTION_B = Section(id="section-b", grade_id="grade-9", name="B", status=SectionStatus.ACTIVE)

OFFERING = GradeSubjectOffering(
    id="off-g9-physics",
    school_id="school-1",
    grade_id="grade-9",
    subject_id="subj-physics",
    assigned_teacher_id="teacher-1",
    academic_session="2025-2026",
    status=OfferingStatus.ACTIVE,
)

LECTURE = SchoolLecture(
    id="lec-1",
    school_id="school-1",
    grade_subject_offering_id="off-g9-physics",
    teacher_user_id="teacher-1",
    title="Newton's Laws",
    topic="Newton's Laws",
    status=LectureStatus.READY_FOR_EDIT,
    current_version_id="ver-1",
)

ENROLLMENT_1 = StudentEnrollment(
    id="enr-1",
    school_id="school-1",
    student_user_id="student-1",
    grade_id="grade-9",
    section_id="section-a",
    academic_session="2025-2026",
    status=StudentEnrollmentStatus.ACTIVE,
    enrolled_at=datetime.now(timezone.utc),
)
ENROLLMENT_2 = StudentEnrollment(
    id="enr-2",
    school_id="school-1",
    student_user_id="student-2",
    grade_id="grade-9",
    section_id="section-b",
    academic_session="2025-2026",
    status=StudentEnrollmentStatus.ACTIVE,
    enrolled_at=datetime.now(timezone.utc),
)
ENROLLMENT_OTHER_GRADE = StudentEnrollment(
    id="enr-3",
    school_id="school-1",
    student_user_id="student-3",
    grade_id="grade-10",
    section_id="section-a",
    academic_session="2025-2026",
    status=StudentEnrollmentStatus.ACTIVE,
    enrolled_at=datetime.now(timezone.utc),
)


class _FakeUserRepo:
    store: dict[str, User] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def get_by_authentik_id(self, authentik_id: str) -> User | None:
        return next((u for u in self.store.values() if u.authentik_id == authentik_id), None)

    async def get_by_id(self, user_id: str) -> User | None:
        return self.store.get(user_id)


class _FakeLectureRepo:
    store: dict[str, SchoolLecture] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def get_by_id(self, lecture_id: str) -> SchoolLecture | None:
        return self.store.get(lecture_id)


class _FakeOfferingRepo:
    store: dict[str, GradeSubjectOffering] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def get_by_id(self, id: str) -> GradeSubjectOffering | None:
        return self.store.get(id)


class _FakeSectionRepo:
    store: dict[str, Section] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def get_by_id(self, id: str) -> Section | None:
        return self.store.get(id)

    async def list_visible_by_grade(self, grade_id: str) -> list[Section]:
        return [s for s in self.store.values() if s.grade_id == grade_id]


class _FakeEnrollmentRepo:
    rows: list[StudentEnrollment] = []

    def __init__(self, session: Any) -> None:
        pass

    async def get_active_by_student_session(
        self, student_user_id: str, academic_session: str
    ) -> StudentEnrollment | None:
        return next(
            (
                e
                for e in self.rows
                if e.student_user_id == student_user_id
                and e.academic_session == academic_session
                and e.status == StudentEnrollmentStatus.ACTIVE
            ),
            None,
        )

    async def list_active_for_grade(
        self, grade_id: str, academic_session: str
    ) -> list[StudentEnrollment]:
        return [
            e
            for e in self.rows
            if e.grade_id == grade_id
            and e.academic_session == academic_session
            and e.status == StudentEnrollmentStatus.ACTIVE
        ]


class _FakeAssignmentRepo:
    rows: list[SchoolLectureAssignment] = []

    def __init__(self, session: Any) -> None:
        pass

    async def list_by_lecture(self, lecture_id: str) -> list[SchoolLectureAssignment]:
        return [r for r in self.rows if r.lecture_id == lecture_id]

    async def replace_for_lecture(
        self, lecture_id: str, assignments: list[SchoolLectureAssignment]
    ) -> list[SchoolLectureAssignment]:
        self.rows[:] = [r for r in self.rows if r.lecture_id != lecture_id]
        for row in assignments:
            row.created_at = datetime.now(timezone.utc)
        self.rows.extend(assignments)
        return assignments


@pytest.fixture(autouse=True)
def _patch_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    _FakeUserRepo.store = {
        u.id: u
        for u in [
            TEACHER,
            OTHER_TEACHER,
            COORDINATOR,
            OTHER_SCHOOL_ADMIN,
            STUDENT_1,
            STUDENT_2,
            STUDENT_OTHER_GRADE,
            STUDENT_UNENROLLED,
        ]
    }
    _FakeLectureRepo.store = {LECTURE.id: LECTURE}
    _FakeOfferingRepo.store = {OFFERING.id: OFFERING}
    _FakeSectionRepo.store = {SECTION_A.id: SECTION_A, SECTION_B.id: SECTION_B}
    _FakeEnrollmentRepo.rows = [ENROLLMENT_1, ENROLLMENT_2, ENROLLMENT_OTHER_GRADE]
    _FakeAssignmentRepo.rows = []
    monkeypatch.setattr("app.features.lectures.service.UserRepository", _FakeUserRepo)
    monkeypatch.setattr("app.features.lectures.service.LectureRepository", _FakeLectureRepo)
    monkeypatch.setattr("app.features.lectures.service.OfferingRepository", _FakeOfferingRepo)
    monkeypatch.setattr("app.features.lectures.service.SectionRepository", _FakeSectionRepo)
    monkeypatch.setattr(
        "app.features.lectures.service.StudentEnrollmentRepository", _FakeEnrollmentRepo
    )
    monkeypatch.setattr(
        "app.features.lectures.service.LectureAssignmentRepository", _FakeAssignmentRepo
    )

    async def _noop_audit(**kwargs: Any) -> None:
        return None

    monkeypatch.setattr("app.features.lectures.service.audit", _noop_audit)


async def _fake_db() -> AsyncGenerator[None, None]:
    yield None


def _claims_for(user: User) -> Any:
    async def _fake_user() -> dict[str, object]:
        return {"sub": user.authentik_id, "role": user.role.value, "user_id": user.id}

    return _fake_user


def _make_client(user: User) -> AsyncClient:
    app = FastAPI()
    setup_exception_handlers(app)
    app.include_router(v1_router, prefix="/api/v1")
    app.dependency_overrides[get_db] = _fake_db
    app.dependency_overrides[get_current_user] = _claims_for(user)
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


# --- API: teacher-owned settings management ---------------------------------


@pytest.mark.asyncio
async def test_default_access_settings_is_unrestricted() -> None:
    async with _make_client(TEACHER) as client:
        res = await client.get("/api/v1/teachers/me/lectures/lec-1/access")

    assert res.status_code == 200
    data = res.json()["data"]
    assert data["is_restricted"] is False
    assert data["assignments"] == []


@pytest.mark.asyncio
async def test_teacher_restricts_to_specific_student() -> None:
    async with _make_client(TEACHER) as client:
        res = await client.put(
            "/api/v1/teachers/me/lectures/lec-1/access",
            json={"assignments": [{"scope": "student", "student_user_id": "student-1"}]},
        )

    assert res.status_code == 200
    data = res.json()["data"]
    assert data["is_restricted"] is True
    assert len(data["assignments"]) == 1
    assert data["assignments"][0]["student_user_id"] == "student-1"
    assert data["assignments"][0]["student_name"] == "Student One"


@pytest.mark.asyncio
async def test_teacher_restricts_to_specific_section() -> None:
    async with _make_client(TEACHER) as client:
        res = await client.put(
            "/api/v1/teachers/me/lectures/lec-1/access",
            json={"assignments": [{"scope": "section", "section_id": "section-a"}]},
        )

    assert res.status_code == 200
    data = res.json()["data"]
    assert data["assignments"][0]["section_id"] == "section-a"
    assert data["assignments"][0]["section_name"] == "A"


@pytest.mark.asyncio
async def test_restricting_to_unenrolled_student_rejected() -> None:
    async with _make_client(TEACHER) as client:
        res = await client.put(
            "/api/v1/teachers/me/lectures/lec-1/access",
            json={"assignments": [{"scope": "student", "student_user_id": "student-4"}]},
        )

    assert res.status_code == 422


@pytest.mark.asyncio
async def test_restricting_to_student_in_wrong_grade_rejected() -> None:
    async with _make_client(TEACHER) as client:
        res = await client.put(
            "/api/v1/teachers/me/lectures/lec-1/access",
            json={"assignments": [{"scope": "student", "student_user_id": "student-3"}]},
        )

    assert res.status_code == 422


@pytest.mark.asyncio
async def test_clearing_assignments_restores_default() -> None:
    async with _make_client(TEACHER) as client:
        await client.put(
            "/api/v1/teachers/me/lectures/lec-1/access",
            json={"assignments": [{"scope": "student", "student_user_id": "student-1"}]},
        )
        res = await client.put(
            "/api/v1/teachers/me/lectures/lec-1/access",
            json={"assignments": []},
        )

    assert res.status_code == 200
    assert res.json()["data"]["is_restricted"] is False


@pytest.mark.asyncio
async def test_non_owning_teacher_cannot_manage_access() -> None:
    async with _make_client(OTHER_TEACHER) as client:
        res = await client.get("/api/v1/teachers/me/lectures/lec-1/access")

    assert res.status_code == 404


# --- API: Coordinator/Admin inheritance (acceptance item 5) -----------------


@pytest.mark.asyncio
async def test_coordinator_in_same_school_can_view_and_override() -> None:
    async with _make_client(COORDINATOR) as client:
        get_res = await client.get("/api/v1/teachers/me/lectures/lec-1/access")
        put_res = await client.put(
            "/api/v1/teachers/me/lectures/lec-1/access",
            json={"assignments": [{"scope": "section", "section_id": "section-b"}]},
        )

    assert get_res.status_code == 200
    assert put_res.status_code == 200
    assert put_res.json()["data"]["assignments"][0]["section_id"] == "section-b"


@pytest.mark.asyncio
async def test_admin_from_a_different_school_cannot_see_lecture() -> None:
    async with _make_client(OTHER_SCHOOL_ADMIN) as client:
        res = await client.get("/api/v1/teachers/me/lectures/lec-1/access")

    assert res.status_code == 404


# --- Service: student_can_access_lecture (acceptance items 1, 3, 4) ---------


@pytest.mark.asyncio
async def test_enrolled_student_has_default_access() -> None:
    svc = LectureWizardService(None)  # type: ignore[arg-type]
    assert await svc.student_can_access_lecture(STUDENT_1, LECTURE) is True


@pytest.mark.asyncio
async def test_unenrolled_student_has_no_access() -> None:
    svc = LectureWizardService(None)  # type: ignore[arg-type]
    assert await svc.student_can_access_lecture(STUDENT_UNENROLLED, LECTURE) is False


@pytest.mark.asyncio
async def test_student_enrolled_in_different_grade_has_no_access() -> None:
    svc = LectureWizardService(None)  # type: ignore[arg-type]
    assert await svc.student_can_access_lecture(STUDENT_OTHER_GRADE, LECTURE) is False


@pytest.mark.asyncio
async def test_restricted_lecture_blocks_non_assigned_enrolled_student() -> None:
    _FakeAssignmentRepo.rows = [
        SchoolLectureAssignment(
            id="assign-1",
            lecture_id="lec-1",
            scope=LectureAssignmentScope.STUDENT,
            student_user_id="student-1",
        )
    ]
    svc = LectureWizardService(None)  # type: ignore[arg-type]
    assert await svc.student_can_access_lecture(STUDENT_1, LECTURE) is True
    assert await svc.student_can_access_lecture(STUDENT_2, LECTURE) is False


@pytest.mark.asyncio
async def test_restricted_lecture_allows_matching_section() -> None:
    _FakeAssignmentRepo.rows = [
        SchoolLectureAssignment(
            id="assign-1",
            lecture_id="lec-1",
            scope=LectureAssignmentScope.SECTION,
            section_id="section-b",
        )
    ]
    svc = LectureWizardService(None)  # type: ignore[arg-type]
    # student-2 is in section-b -> allowed; student-1 is in section-a -> blocked.
    assert await svc.student_can_access_lecture(STUDENT_2, LECTURE) is True
    assert await svc.student_can_access_lecture(STUDENT_1, LECTURE) is False


# --- API: roster picker source -----------------------------------------------


@pytest.mark.asyncio
async def test_roster_lists_sections_and_enrolled_students() -> None:
    async with _make_client(TEACHER) as client:
        res = await client.get("/api/v1/teachers/me/lectures/lec-1/roster")

    assert res.status_code == 200
    data = res.json()["data"]
    section_ids = {s["id"] for s in data["sections"]}
    assert section_ids == {"section-a", "section-b"}
    student_ids = {s["id"] for s in data["students"]}
    # student-3 is enrolled in a different grade, so it's excluded from this roster.
    assert student_ids == {"student-1", "student-2"}
