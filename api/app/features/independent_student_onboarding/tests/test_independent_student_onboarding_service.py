"""Tests for independent student onboarding derived state."""

from __future__ import annotations

from datetime import date, datetime, timezone

from app.features.independent_student_onboarding.models import IndependentStudentProfile
from app.features.independent_student_onboarding.schemas import IndependentStudentOnboardingState
from app.features.independent_student_onboarding.service import derive_independent_student_state


def test_derive_state_missing_exam_date() -> None:
    profile = IndependentStudentProfile(
        user_id="user-1",
        name="Sara",
        language_preference="en",
        grade_level=10,
        exam_syllabus_id="syllabus-1",
    )
    state = derive_independent_student_state(profile=profile)
    assert state.state == IndependentStudentOnboardingState.PROFILE_INCOMPLETE
    assert state.ready_to_study is False


def test_derive_state_ready_to_study() -> None:
    profile = IndependentStudentProfile(
        user_id="user-1",
        name="Sara",
        language_preference="en",
        grade_level=10,
        exam_syllabus_id="syllabus-1",
        exam_date=date(2026, 12, 1),
        profile_completed_at=datetime.now(timezone.utc),
    )
    state = derive_independent_student_state(profile=profile)
    assert state.state == IndependentStudentOnboardingState.READY_TO_STUDY
    assert state.ready_to_study is True
    assert state.self_study_only is True
