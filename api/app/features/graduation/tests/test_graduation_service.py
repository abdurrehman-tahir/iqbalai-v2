"""Graduation service tests — T-085/T-086."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.features.grades.models import Grade
from app.features.graduation.models import GraduationMigrationLog, GraduationMigrationStatus
from app.features.graduation.service import GraduationService
from app.features.student_enrollments.models import StudentEnrollment, StudentEnrollmentStatus
from app.features.student_onboarding.models import StudentProfile
from app.features.student_onboarding.schemas import SchoolStudentOnboardingState
from app.features.student_onboarding.service import derive_school_student_state
from app.features.users.models import User, UserAccountStatus, UserRole


class _FakeUserRepo:
    store: dict[str, User] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def get_by_authentik_id(self, authentik_id: str) -> User | None:
        return next((u for u in self.store.values() if u.authentik_id == authentik_id), None)

    async def get_by_id(self, user_id: str) -> User | None:
        return self.store.get(user_id)


class _FakeProfileRepo:
    store: dict[str, StudentProfile] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def get_by_user_id(self, user_id: str) -> StudentProfile | None:
        return self.store.get(user_id)

    async def update(self, profile: StudentProfile) -> StudentProfile:
        self.store[profile.user_id] = profile
        return profile


class _FakeEnrollmentRepo:
    store: dict[str, StudentEnrollment] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def list_for_student(self, student_user_id: str) -> list[StudentEnrollment]:
        return [e for e in self.store.values() if e.student_user_id == student_user_id]

    async def update(self, enrollment: StudentEnrollment) -> StudentEnrollment:
        self.store[enrollment.id] = enrollment
        return enrollment


COORDINATOR = User(
    id="coord-1",
    authentik_id="auth-coord",
    email="coord@example.com",
    display_name="Coordinator",
    role=UserRole.COORDINATOR,
    status=UserAccountStatus.ACTIVE,
    school_id="school-1",
    scoped_ids="Grade 12",
)
STUDENT = User(
    id="student-1",
    authentik_id="auth-student",
    email="student@example.com",
    display_name="Student One",
    role=UserRole.STUDENT,
    status=UserAccountStatus.ACTIVE,
    school_id="school-1",
)
ADMIN = User(
    id="admin-1",
    authentik_id="auth-admin",
    email="admin@example.com",
    display_name="School Admin",
    role=UserRole.SCHOOL_ADMIN,
    status=UserAccountStatus.ACTIVE,
    school_id="school-1",
)
ENROLLMENT = StudentEnrollment(
    id="enroll-1",
    school_id="school-1",
    student_user_id=STUDENT.id,
    grade_id="grade-12",
    section_id="section-a",
    academic_session="2025-26",
    status=StudentEnrollmentStatus.ACTIVE,
    enrolled_at=datetime.now(timezone.utc),
)
PROFILE = StudentProfile(
    user_id=STUDENT.id,
    display_name="Student One",
    language_preference="en",
    lecture_mode_enabled=True,
    self_study_mode_enabled=True,
    profile_basic_completed_at=datetime.now(timezone.utc),
)


@pytest.fixture(autouse=True)
def _patch_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    _FakeUserRepo.store = {
        COORDINATOR.id: COORDINATOR,
        STUDENT.id: STUDENT,
        ADMIN.id: ADMIN,
    }
    _FakeProfileRepo.store = {STUDENT.id: PROFILE}
    _FakeEnrollmentRepo.store = {ENROLLMENT.id: ENROLLMENT}

    monkeypatch.setattr("app.features.graduation.service.UserRepository", _FakeUserRepo)
    monkeypatch.setattr("app.features.graduation.service.StudentProfileRepository", _FakeProfileRepo)
    monkeypatch.setattr("app.features.graduation.service.StudentEnrollmentRepository", _FakeEnrollmentRepo)
    monkeypatch.setattr("app.features.graduation.service.GraduationRequestRepository", MagicMock())
    monkeypatch.setattr("app.features.graduation.service.GraduationMigrationLogRepository", MagicMock())
    monkeypatch.setattr("app.features.graduation.service.ParentChildLinkRepository", MagicMock())
    monkeypatch.setattr("app.features.graduation.service.IndependentUserRepository", MagicMock())
    monkeypatch.setattr("app.features.graduation.service.IndependentStudentProfileRepository", MagicMock())
    monkeypatch.setattr("app.features.graduation.service.ExamSyllabiRepository", MagicMock())
    monkeypatch.setattr("app.features.graduation.service.audit", AsyncMock())
    monkeypatch.setattr("app.features.graduation.service.notify_account_event", AsyncMock())
    monkeypatch.setattr("app.features.graduation.service.publish_graduation_event", AsyncMock())

    async def _get_grade(grade_id: str) -> Grade:
        return Grade(
            id=grade_id,
            school_id="school-1",
            name="Grade 12",
            academic_session="2025-26",
            level_ordinal=12,
        )

    monkeypatch.setattr(GraduationService, "_get_grade", _get_grade)


def test_derive_school_read_only_state() -> None:
    graduated_profile = StudentProfile(
        user_id=STUDENT.id,
        display_name="Student One",
        language_preference="en",
        lecture_mode_enabled=True,
        self_study_mode_enabled=True,
        is_graduated=True,
        graduated_at=datetime.now(timezone.utc),
    )
    state = derive_school_student_state(
        user=STUDENT,
        profile=graduated_profile,
        enrollment_grade_id="grade-12",
        migration_scheduled_at=datetime.now(timezone.utc) + timedelta(days=180),
    )
    assert state.state is SchoolStudentOnboardingState.SCHOOL_READ_ONLY
    assert state.school_read_only is True
    assert state.lecture_read_only is True
    assert state.self_study_enabled is True
    assert state.graduation_message is not None


def test_build_graduation_status_for_graduated_student() -> None:
    profile = StudentProfile(
        user_id=STUDENT.id,
        display_name="Student One",
        language_preference="en",
        is_graduated=True,
        graduated_at=datetime.now(timezone.utc),
    )
    log = GraduationMigrationLog(
        student_user_id=STUDENT.id,
        graduated_at=profile.graduated_at,
        migration_scheduled_at=datetime.now(timezone.utc) + timedelta(days=180),
        migration_status=GraduationMigrationStatus.PENDING,
    )
    svc = GraduationService(AsyncMock())
    status = svc.build_student_graduation_status(profile=profile, migration_log=log)
    assert status.school_read_only is True
    assert status.lecture_read_only is True
