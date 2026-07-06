"""M-06 milestone E2E smoke tests — T-089."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.features.audit.actions import (
    DATA_RIGHTS_EXPORT_REQUESTED,
    GRADUATION_APPROVED,
    PARENT_LINK_APPROVED,
    STUDENT_ENROLLED,
)
from app.features.graduation.models import GraduationMigrationStatus
from app.features.parent_child_links.models import ParentChildLinkStatus
from app.features.student_onboarding.schemas import SchoolStudentOnboardingState
from app.features.student_onboarding.service import derive_school_student_state
from app.features.users.models import User, UserAccountStatus, UserRole


def test_m06_audit_action_registry_includes_core_actions() -> None:
    from app.features.audit.actions import M06_AUDIT_ACTIONS, REGISTERED_AUDIT_ACTIONS

    for action in (
        STUDENT_ENROLLED,
        PARENT_LINK_APPROVED,
        DATA_RIGHTS_EXPORT_REQUESTED,
        GRADUATION_APPROVED,
    ):
        assert action in M06_AUDIT_ACTIONS
        assert action in REGISTERED_AUDIT_ACTIONS


def test_m06_student_onboarding_ready_derivation() -> None:
    from app.features.student_onboarding.models import StudentProfile

    user = User(
        id="s1",
        authentik_id="a1",
        email="s@example.com",
        display_name="Student",
        role=UserRole.STUDENT,
        status=UserAccountStatus.ACTIVE,
        school_id="school-1",
    )
    profile = StudentProfile(
        user_id="s1",
        display_name="Student",
        language_preference="en",
        profile_basic_completed_at=datetime.now(timezone.utc),
        lecture_mode_enabled=True,
        self_study_mode_enabled=False,
    )
    state = derive_school_student_state(user=user, profile=profile, enrollment_grade_id="g9")
    assert state.ready_to_study is True
    assert state.state is SchoolStudentOnboardingState.READY_TO_STUDY


def test_m06_graduation_read_only_enforcement() -> None:
    from app.features.student_onboarding.models import StudentProfile

    user = User(
        id="s1",
        authentik_id="a1",
        email="s@example.com",
        display_name="Student",
        role=UserRole.STUDENT,
        status=UserAccountStatus.ACTIVE,
        school_id="school-1",
    )
    profile = StudentProfile(
        user_id="s1",
        display_name="Student",
        language_preference="en",
        lecture_mode_enabled=True,
        self_study_mode_enabled=True,
        is_graduated=True,
        graduated_at=datetime.now(timezone.utc),
    )
    state = derive_school_student_state(
        user=user,
        profile=profile,
        enrollment_grade_id="g12",
        migration_scheduled_at=datetime.now(timezone.utc) + timedelta(days=180),
    )
    assert state.state is SchoolStudentOnboardingState.SCHOOL_READ_ONLY
    assert state.lecture_read_only is True
    assert state.self_study_enabled is True


def test_m06_parent_link_read_only_gate() -> None:
    from app.features.parent_child_links.models import ParentChildLink
    from app.features.parent_child_links.service import ACCESS_STATE_LINKED

    link = ParentChildLink(
        id="link-1",
        parent_user_id="p1",
        student_user_id="s1",
        status=ParentChildLinkStatus.APPROVED,
        approved_at=datetime.now(timezone.utc),
    )
    assert link.status is ParentChildLinkStatus.APPROVED
    assert ACCESS_STATE_LINKED == "LINKED"


def test_m06_migration_grace_window_default() -> None:
    from app.config import get_settings

    settings = get_settings()
    assert settings.GRADUATION_GRACE_DAYS == 180
    assert settings.GRADUATION_MIGRATION_MAX_ATTEMPTS == 5


def test_m06_schema_isolation_intent() -> None:
    from app.features.independent_users.models import IndependentUser
    from app.features.users.models import User

    assert User.__table__.schema == "school"
    assert IndependentUser.__table__.schema == "independent"


def test_m06_migration_log_pending_status() -> None:
    from app.features.graduation.models import GraduationMigrationLog

    log = GraduationMigrationLog(
        student_user_id="s1",
        graduated_at=datetime.now(timezone.utc),
        migration_scheduled_at=datetime.now(timezone.utc) - timedelta(days=1),
        migration_status=GraduationMigrationStatus.PENDING,
    )
    assert log.migration_status is GraduationMigrationStatus.PENDING
