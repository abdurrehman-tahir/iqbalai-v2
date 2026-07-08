"""Unit tests for school student onboarding state — T-078."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from app.core.exceptions import ConflictError
from app.features.student_onboarding.models import StudentProfile
from app.features.student_onboarding.schemas import SchoolStudentOnboardingState
from app.features.student_onboarding.service import StudentOnboardingService, derive_school_student_state
from app.features.users.models import User, UserAccountStatus, UserRole


def _student(status: UserAccountStatus = UserAccountStatus.ACTIVE) -> User:
    return User(
        id="student-1",
        authentik_id="student-1",
        email="student@test.com",
        display_name="Student",
        role=UserRole.STUDENT,
        status=status,
        school_id="school-1",
    )


def test_derive_invited_state() -> None:
    state = derive_school_student_state(
        user=_student(UserAccountStatus.INVITED),
        profile=None,
        enrollment_grade_id="grade-9",
    )
    assert state.state == SchoolStudentOnboardingState.INVITED
    assert not state.ready_to_study


def test_derive_profile_basic_state() -> None:
    state = derive_school_student_state(user=_student(), profile=None, enrollment_grade_id="grade-9")
    assert state.state == SchoolStudentOnboardingState.PROFILE_BASIC


def test_derive_ready_to_study() -> None:
    profile = StudentProfile(
        user_id="student-1",
        display_name="Ali",
        language_preference="en",
        tos_accepted_at=datetime.now(timezone.utc),
        profile_basic_completed_at=datetime.now(timezone.utc),
        lecture_mode_enabled=True,
        self_study_mode_enabled=False,
        deferrable_banner_dismissed=False,
    )
    state = derive_school_student_state(
        user=_student(), profile=profile, enrollment_grade_id="grade-9"
    )
    assert state.state == SchoolStudentOnboardingState.READY_TO_STUDY
    assert state.ready_to_study
    assert state.show_complete_profile_banner


@pytest.mark.asyncio
async def test_complete_profile_basic_creates_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.features.student_onboarding.service.audit", AsyncMock())
    svc = StudentOnboardingService(AsyncMock())
    svc._require_student = AsyncMock(return_value=_student())
    svc._profile_repo.get_by_user_id = AsyncMock(return_value=None)
    svc._profile_repo.create = AsyncMock(
        side_effect=lambda p: p,
    )
    svc._user_repo.update = AsyncMock()
    svc._tos.accept_tos = AsyncMock()
    svc._active_enrollment_grade_id = AsyncMock(return_value="grade-9")
    svc._session = AsyncMock()

    from app.features.student_onboarding.schemas import StudentProfileBasicComplete

    state = await svc.complete_profile_basic(
        StudentProfileBasicComplete(
            display_name="Ali Khan",
            language_preference="en",
            tos_version_id="tos-1",
        ),
        {"sub": "student-1"},
        actor_id="student-1",
    )
    assert state.profile_basic_complete
    assert state.state == SchoolStudentOnboardingState.MODE_SELECTION


@pytest.mark.asyncio
async def test_complete_profile_basic_ignores_already_accepted_tos(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.features.student_onboarding.service.audit", AsyncMock())
    svc = StudentOnboardingService(AsyncMock())
    svc._require_student = AsyncMock(return_value=_student())
    svc._profile_repo.get_by_user_id = AsyncMock(return_value=None)
    svc._profile_repo.create = AsyncMock(side_effect=lambda p: p)
    svc._user_repo.update = AsyncMock()
    svc._tos.accept_tos = AsyncMock(side_effect=ConflictError("ToS version already accepted"))
    svc._active_enrollment_grade_id = AsyncMock(return_value="grade-9")
    svc._session = AsyncMock()

    from app.features.student_onboarding.schemas import StudentProfileBasicComplete

    state = await svc.complete_profile_basic(
        StudentProfileBasicComplete(
            display_name="Ali Khan",
            language_preference="en",
            tos_version_id="tos-1",
        ),
        {"sub": "student-1"},
        actor_id="student-1",
    )
    assert state.profile_basic_complete
    assert state.state == SchoolStudentOnboardingState.MODE_SELECTION
