"""Tests for independent teacher onboarding derived state."""

from __future__ import annotations

from datetime import datetime, timezone

from app.features.independent_teacher_onboarding.models import IndependentTeacherProfile
from app.features.independent_teacher_onboarding.schemas import IndependentTeacherOnboardingState
from app.features.independent_teacher_onboarding.service import derive_independent_teacher_state
from app.features.independent_users.models import IndependentUserAccountStatus


def test_derive_state_profile_incomplete() -> None:
    state = derive_independent_teacher_state(
        profile=None,
        account_status=IndependentUserAccountStatus.ACTIVE,
    )
    assert state.state == IndependentTeacherOnboardingState.PROFILE_INCOMPLETE
    assert state.ready_to_use is False
    assert state.can_create_content is False


def test_derive_state_ready_to_use() -> None:
    profile = IndependentTeacherProfile(
        user_id="user-1",
        name="Ali",
        language_preference="en",
        profile_completed_at=datetime.now(timezone.utc),
    )
    state = derive_independent_teacher_state(
        profile=profile,
        account_status=IndependentUserAccountStatus.ACTIVE,
    )
    assert state.state == IndependentTeacherOnboardingState.READY_TO_USE
    assert state.ready_to_use is True
    assert state.can_create_content is True


def test_derive_state_suspended_blocks_content() -> None:
    profile = IndependentTeacherProfile(
        user_id="user-1",
        name="Ali",
        language_preference="en",
        profile_completed_at=datetime.now(timezone.utc),
    )
    state = derive_independent_teacher_state(
        profile=profile,
        account_status=IndependentUserAccountStatus.SUSPENDED,
    )
    assert state.ready_to_use is True
    assert state.can_create_content is False
