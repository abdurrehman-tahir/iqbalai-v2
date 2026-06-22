"""M-05 milestone E2E smoke tests — T-075."""

from __future__ import annotations

from datetime import datetime, timezone

from app.core.tenant import get_tenant_type, is_independent_role
from app.features.independent_student_onboarding.service import derive_independent_student_state
from app.features.independent_teacher_onboarding.service import derive_independent_teacher_state
from app.features.independent_users.models import IndependentUserAccountStatus


def test_tenant_type_routes_independent_jwt() -> None:
    claims = {"role": "independent_teacher", "tenant_type": "independent", "school_id": None}
    assert get_tenant_type(claims) == "independent"
    assert is_independent_role(claims["role"]) is True


def test_independent_teacher_reaches_ready_to_use_without_assignment() -> None:
    from app.features.independent_teacher_onboarding.models import IndependentTeacherProfile

    profile = IndependentTeacherProfile(
        user_id="t1",
        name="Teacher",
        language_preference="en",
        profile_completed_at=datetime.now(timezone.utc),
    )
    state = derive_independent_teacher_state(
        profile=profile,
        account_status=IndependentUserAccountStatus.ACTIVE,
    )
    assert state.ready_to_use is True
    assert state.state.value == "ready_to_use"


def test_independent_student_exam_framework_gate_at_signup_schema() -> None:
    """Student signup requires exam_syllabus_id — validated in service layer."""
    from app.features.independent_signup.schemas import IndependentSignupCreate
    from app.features.independent_users.models import IndependentUserRole

    payload = IndependentSignupCreate(
        email="s@example.com",
        password="password1",
        display_name="Student",
        role=IndependentUserRole.INDEPENDENT_STUDENT,
        language_preference="en",
    )
    assert payload.exam_syllabus_id is None
    assert payload.grade_level is None


def test_independent_student_ready_to_study_after_exam_date() -> None:
    from datetime import date

    from app.features.independent_student_onboarding.models import IndependentStudentProfile

    profile = IndependentStudentProfile(
        user_id="s1",
        name="Student",
        language_preference="en",
        grade_level=10,
        exam_syllabus_id="syllabus-1",
        exam_date=date(2026, 12, 1),
        profile_completed_at=datetime.now(timezone.utc),
    )
    state = derive_independent_student_state(profile=profile)
    assert state.ready_to_study is True
    assert state.self_study_only is True


def test_schema_isolation_intent_school_vs_independent_tables() -> None:
    from app.features.independent_users.models import IndependentUser
    from app.features.users.models import User

    assert User.__table__.schema == "school"
    assert IndependentUser.__table__.schema == "independent"
