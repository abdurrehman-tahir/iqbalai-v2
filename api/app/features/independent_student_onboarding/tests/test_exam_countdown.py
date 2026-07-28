"""Independent exam countdown / passed delivery — T-107."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock

import pytest

from app.features.independent_student_onboarding.models import IndependentStudentProfile
from app.features.independent_student_onboarding.service import (
    IndependentStudentOnboardingService,
    derive_independent_student_state,
)
from app.features.independent_users.models import (
    IndependentUser,
    IndependentUserAccountStatus,
    IndependentUserRole,
)


class _FakeProfileRepo:
    store: dict[str, IndependentStudentProfile] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def get_by_user_id(self, user_id: str) -> IndependentStudentProfile | None:
        return self.store.get(user_id)

    async def update(self, profile: IndependentStudentProfile) -> IndependentStudentProfile:
        self.store[profile.user_id] = profile
        return profile

    async def list_with_exam_dates(self) -> list[IndependentStudentProfile]:
        return [p for p in self.store.values() if p.exam_date is not None]


class _FakeUserRepo:
    store: dict[str, IndependentUser] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def get_by_id(self, user_id: str) -> IndependentUser | None:
        return self.store.get(user_id)

    async def get_by_authentik_id(self, authentik_id: str) -> IndependentUser | None:
        return next((u for u in self.store.values() if u.authentik_id == authentik_id), None)


USER = IndependentUser(
    id="ind-1",
    authentik_id="auth-ind",
    email="ind@example.com",
    display_name="Ind Student",
    role=IndependentUserRole.INDEPENDENT_STUDENT,
    status=IndependentUserAccountStatus.ACTIVE,
)

PROFILE = IndependentStudentProfile(
    user_id=USER.id,
    name="Ind Student",
    language_preference="en",
    grade_level=10,
    exam_syllabus_id="syl-1",
    exam_date=date.today() + timedelta(days=30),
    profile_completed_at=datetime.now(timezone.utc),
)


@pytest.fixture(autouse=True)
def _patch(monkeypatch: pytest.MonkeyPatch) -> None:
    _FakeProfileRepo.store = {
        USER.id: IndependentStudentProfile(
            user_id=USER.id,
            name="Ind Student",
            language_preference="en",
            grade_level=10,
            exam_syllabus_id="syl-1",
            exam_date=date.today() + timedelta(days=30),
            profile_completed_at=datetime.now(timezone.utc),
        )
    }
    _FakeUserRepo.store = {USER.id: USER}
    monkeypatch.setattr(
        "app.features.independent_student_onboarding.service.IndependentStudentProfileRepository",
        _FakeProfileRepo,
    )
    monkeypatch.setattr(
        "app.features.independent_student_onboarding.service.IndependentUserRepository",
        _FakeUserRepo,
    )


@pytest.mark.asyncio
async def test_independent_countdown_and_passed(monkeypatch: pytest.MonkeyPatch) -> None:
    notify = AsyncMock()
    monkeypatch.setattr(
        "app.infrastructure.notifications.self_study.notify_self_study_event",
        notify,
    )
    svc = IndependentStudentOnboardingService(AsyncMock())
    assert await svc.send_exam_countdown_notifications() == 1
    assert _FakeProfileRepo.store[USER.id].exam_countdown_sent_days == "30"

    profile = _FakeProfileRepo.store[USER.id]
    profile.exam_date = date.today() - timedelta(days=1)
    assert await svc.send_exam_countdown_notifications() == 1
    assert notify.await_args is not None
    assert notify.await_args.kwargs["template_key"] == "self_study.exam_passed"
    assert "passed" in (profile.exam_countdown_sent_days or "")


def test_derive_exam_date_passed() -> None:
    profile = IndependentStudentProfile(
        user_id=USER.id,
        name="Ind",
        language_preference="en",
        grade_level=10,
        exam_syllabus_id="syl-1",
        exam_date=date.today() - timedelta(days=3),
        profile_completed_at=datetime.now(timezone.utc),
    )
    state = derive_independent_student_state(profile=profile)
    assert state.exam_date_passed is True
