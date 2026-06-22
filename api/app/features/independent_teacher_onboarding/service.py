"""Independent teacher onboarding business logic — T-070."""

from __future__ import annotations

from datetime import datetime, timezone

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, PermissionDeniedError, PreconditionFailedError
from app.features.independent_teacher_onboarding.models import IndependentTeacherProfile
from app.features.independent_teacher_onboarding.repository import IndependentTeacherProfileRepository
from app.features.independent_teacher_onboarding.schemas import (
    IndependentTeacherOnboardingRead,
    IndependentTeacherOnboardingState,
    IndependentTeacherProfileComplete,
    IndependentTeacherProfileRead,
)
from app.features.independent_users.models import IndependentUser, IndependentUserAccountStatus, IndependentUserRole
from app.features.independent_users.repository import IndependentUserRepository

logger = structlog.get_logger(__name__)


def derive_independent_teacher_state(
    *,
    profile: IndependentTeacherProfile | None,
    account_status: IndependentUserAccountStatus,
) -> IndependentTeacherOnboardingRead:
    profile_complete = profile is not None and profile.profile_completed_at is not None
    ready_to_use = profile_complete
    state = (
        IndependentTeacherOnboardingState.READY_TO_USE
        if ready_to_use
        else IndependentTeacherOnboardingState.PROFILE_INCOMPLETE
    )
    can_create_content = account_status == IndependentUserAccountStatus.ACTIVE and ready_to_use
    profile_read = (
        IndependentTeacherProfileRead.model_validate(profile) if profile is not None else None
    )
    return IndependentTeacherOnboardingRead(
        state=state,
        profile_complete=profile_complete,
        ready_to_use=ready_to_use,
        can_create_content=can_create_content,
        profile=profile_read,
    )


class IndependentTeacherOnboardingService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._profile_repo = IndependentTeacherProfileRepository(session)
        self._user_repo = IndependentUserRepository(session)

    async def _require_independent_teacher(self, claims: dict[str, object]) -> IndependentUser:
        user = await self._user_repo.get_by_authentik_id(str(claims.get("sub", "")))
        if user is None or user.deleted_at is not None:
            raise NotFoundError("User profile not found")
        if user.role != IndependentUserRole.INDEPENDENT_TEACHER:
            raise PermissionDeniedError("Independent teacher onboarding only for independent teachers")
        return user

    async def get_onboarding_state(
        self, claims: dict[str, object]
    ) -> IndependentTeacherOnboardingRead:
        user = await self._require_independent_teacher(claims)
        profile = await self._profile_repo.get_by_user_id(user.id)
        return derive_independent_teacher_state(profile=profile, account_status=user.status)

    async def complete_profile(
        self,
        payload: IndependentTeacherProfileComplete,
        claims: dict[str, object],
    ) -> IndependentTeacherOnboardingRead:
        user = await self._require_independent_teacher(claims)
        if user.status == IndependentUserAccountStatus.SUSPENDED:
            raise PermissionDeniedError(
                "Suspended teachers cannot complete profile or create new content"
            )

        profile = await self._profile_repo.get_by_user_id(user.id)
        now = datetime.now(timezone.utc)
        if profile is None:
            profile = IndependentTeacherProfile(
                user_id=user.id,
                name=payload.name.strip(),
                language_preference=payload.language_preference,
                profile_completed_at=now,
            )
            profile = await self._profile_repo.create(profile)
        elif profile.profile_completed_at is None:
            profile.name = payload.name.strip()
            profile.language_preference = payload.language_preference
            profile.profile_completed_at = now
            profile = await self._profile_repo.update(profile)
        else:
            raise PreconditionFailedError("Profile is already complete")

        user.display_name = profile.name
        user.language_preference = profile.language_preference
        await self._user_repo.update(user)

        logger.info("independent_teacher_profile_completed", user_id=user.id)
        return derive_independent_teacher_state(profile=profile, account_status=user.status)
