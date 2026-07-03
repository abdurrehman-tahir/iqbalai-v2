"""Independent student onboarding business logic — T-071."""

from __future__ import annotations

from datetime import datetime, timezone

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, PermissionDeniedError, PreconditionFailedError
from app.features.exam_syllabi.repository import ExamSyllabiRepository
from app.features.independent_student_onboarding.models import IndependentStudentProfile
from app.features.independent_student_onboarding.repository import IndependentStudentProfileRepository
from app.features.independent_student_onboarding.schemas import (
    ExamFrameworkOption,
    IndependentStudentOnboardingRead,
    IndependentStudentOnboardingState,
    IndependentStudentProfileComplete,
    IndependentStudentProfileRead,
)
from app.features.independent_users.models import IndependentUser, IndependentUserAccountStatus, IndependentUserRole
from app.features.independent_users.repository import IndependentUserRepository

logger = structlog.get_logger(__name__)


def derive_independent_student_state(
    *,
    profile: IndependentStudentProfile | None,
) -> IndependentStudentOnboardingRead:
    profile_complete = (
        profile is not None
        and profile.profile_completed_at is not None
        and profile.exam_date is not None
    )
    ready_to_study = profile_complete
    state = (
        IndependentStudentOnboardingState.READY_TO_STUDY
        if ready_to_study
        else IndependentStudentOnboardingState.PROFILE_INCOMPLETE
    )
    profile_read = None
    if profile is not None:
        profile_read = IndependentStudentProfileRead.model_validate(profile)
        profile_read.diagnostic_available = True
        profile_read.diagnostic_deferred = True
    return IndependentStudentOnboardingRead(
        state=state,
        profile_complete=profile_complete,
        ready_to_study=ready_to_study,
        self_study_only=True,
        profile=profile_read,
    )


class IndependentStudentOnboardingService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._profile_repo = IndependentStudentProfileRepository(session)
        self._user_repo = IndependentUserRepository(session)
        self._syllabi_repo = ExamSyllabiRepository(session)

    async def list_exam_frameworks(self) -> list[ExamFrameworkOption]:
        syllabi = await self._syllabi_repo.list_syllabi()
        return [
            ExamFrameworkOption(
                id=s.id,
                name=s.name,
                exam_board=s.exam_board,
                language=s.language,
            )
            for s in syllabi
            if s.deleted_at is None
        ]

    async def _require_independent_student(self, claims: dict[str, object]) -> IndependentUser:
        user = await self._user_repo.get_by_authentik_id(str(claims.get("sub", "")))
        if user is None or user.deleted_at is not None:
            raise NotFoundError("User profile not found")
        if user.role != IndependentUserRole.INDEPENDENT_STUDENT:
            raise PermissionDeniedError("Independent student onboarding only for independent students")
        return user

    async def get_onboarding_state(
        self, claims: dict[str, object]
    ) -> IndependentStudentOnboardingRead:
        user = await self._require_independent_student(claims)
        profile = await self._profile_repo.get_by_user_id(user.id)
        return derive_independent_student_state(profile=profile)

    async def complete_profile(
        self,
        payload: IndependentStudentProfileComplete,
        claims: dict[str, object],
    ) -> IndependentStudentOnboardingRead:
        user = await self._require_independent_student(claims)
        if user.status == IndependentUserAccountStatus.SUSPENDED:
            raise PermissionDeniedError("Suspended students cannot update profile")

        profile = await self._profile_repo.get_by_user_id(user.id)
        if profile is None:
            raise NotFoundError("Student signup profile missing — contact support")

        if profile.profile_completed_at is not None:
            raise PreconditionFailedError("Profile is already complete")

        now = datetime.now(timezone.utc)
        profile.exam_date = payload.exam_date
        profile.profile_completed_at = now
        profile = await self._profile_repo.update(profile)

        logger.info("independent_student_profile_completed", user_id=user.id)
        return derive_independent_student_state(profile=profile)
