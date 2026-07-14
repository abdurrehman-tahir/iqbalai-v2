"""Teacher onboarding business logic — T-053."""

from __future__ import annotations

from datetime import datetime, timezone

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, PermissionDeniedError, PreconditionFailedError
from app.features.audit.actions import CAPACITY_UPDATED
from app.features.offerings.repository import OfferingRepository
from app.features.offerings.service import DEFAULT_TEACHER_CAPACITY
from app.features.subjects.models import Subject, SubjectStatus
from app.features.subjects.repository import SubjectRepository
from app.features.teacher_onboarding.models import TeacherProfile
from app.features.teacher_onboarding.repository import TeacherProfileRepository
from app.features.teacher_onboarding.schemas import (
    TeacherCapacityUpdate,
    TeacherCapacityUpdateRead,
    TeacherOnboardingRead,
    TeacherOnboardingState,
    TeacherProfileComplete,
    TeacherProfileRead,
)
from app.features.users.models import User, UserAccountStatus, UserRole
from app.features.users.repository import UserRepository
from app.infrastructure.audit.log import audit
from app.infrastructure.notifications.account import notify_account_event

logger = structlog.get_logger(__name__)


def derive_onboarding_state(
    *,
    profile: TeacherProfile | None,
    assignment_count: int,
    account_status: UserAccountStatus,
    teacher_capacity: int | None = None,
) -> TeacherOnboardingRead:
    """Compute onboarding gate state server-side (never store ready_to_teach)."""
    capacity = teacher_capacity if teacher_capacity is not None else DEFAULT_TEACHER_CAPACITY
    profile_complete = profile is not None and profile.profile_completed_at is not None
    ready_to_teach = profile_complete and assignment_count >= 1
    capacity_below_assignments = capacity < assignment_count

    if not profile_complete:
        state = TeacherOnboardingState.PROFILE_INCOMPLETE
    elif ready_to_teach:
        state = TeacherOnboardingState.READY_TO_TEACH
    else:
        state = TeacherOnboardingState.PROFILE_COMPLETE

    can_create_content = account_status == UserAccountStatus.ACTIVE and ready_to_teach

    profile_read = TeacherProfileRead.model_validate(profile) if profile is not None else None
    return TeacherOnboardingRead(
        state=state,
        profile_complete=profile_complete,
        ready_to_teach=ready_to_teach,
        assignment_count=assignment_count,
        can_create_content=can_create_content,
        teacher_capacity=capacity,
        capacity_below_assignments=capacity_below_assignments,
        profile=profile_read,
    )


class TeacherOnboardingService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._profile_repo = TeacherProfileRepository(session)
        self._user_repo = UserRepository(session)
        self._offering_repo = OfferingRepository(session)
        self._subject_repo = SubjectRepository(session)

    async def _require_teacher(self, claims: dict[str, object]) -> User:
        user = await self._user_repo.get_by_authentik_id(str(claims.get("sub", "")))
        if user is None or user.deleted_at is not None:
            raise NotFoundError("User profile not found")
        if user.role != UserRole.TEACHER:
            raise PermissionDeniedError("School teacher onboarding is only for teachers")
        if user.school_id is None:
            raise PermissionDeniedError("Teacher must belong to a school")
        return user

    async def get_onboarding_state(self, claims: dict[str, object]) -> TeacherOnboardingRead:
        user = await self._require_teacher(claims)
        profile = await self._profile_repo.get_by_user_id(user.id)
        assignment_count = await self._offering_repo.count_active_assignments_for_teacher(user.id)
        return derive_onboarding_state(
            profile=profile,
            assignment_count=assignment_count,
            account_status=user.status,
            teacher_capacity=user.teacher_capacity,
        )

    async def _validate_subject_ids(self, school_id: str, subject_ids: list[str]) -> None:
        subjects = await self._subject_repo.list_by_school(school_id, include_archived=False)
        valid_ids = {subject.id for subject in subjects if subject.status == SubjectStatus.ACTIVE}
        invalid = [sid for sid in subject_ids if sid not in valid_ids]
        if invalid:
            raise PreconditionFailedError(
                f"Unknown or inactive subject IDs for this school: {', '.join(invalid)}"
            )

    async def complete_profile(
        self,
        payload: TeacherProfileComplete,
        claims: dict[str, object],
    ) -> TeacherOnboardingRead:
        user = await self._require_teacher(claims)
        if user.status == UserAccountStatus.SUSPENDED:
            raise PermissionDeniedError(
                "Suspended teachers cannot complete profile or create new content"
            )

        await self._validate_subject_ids(user.school_id or "", payload.subject_ids)

        profile = await self._profile_repo.get_by_user_id(user.id)
        now = datetime.now(timezone.utc)
        if profile is None:
            profile = TeacherProfile(
                user_id=user.id,
                name=payload.name.strip(),
                region_province=payload.region_province,
                region_district=(payload.region_district or "").strip() or None,
                bio=(payload.bio or "").strip() or None,
                language_preference=payload.language_preference,
                subject_ids=payload.subject_ids,
                profile_completed_at=now,
            )
            profile = await self._profile_repo.create(profile)
        elif profile.profile_completed_at is None:
            profile.name = payload.name.strip()
            profile.region_province = payload.region_province
            profile.region_district = (payload.region_district or "").strip() or None
            profile.bio = (payload.bio or "").strip() or None
            profile.language_preference = payload.language_preference
            profile.subject_ids = payload.subject_ids
            profile.profile_completed_at = now
            profile = await self._profile_repo.update(profile)
        else:
            raise PreconditionFailedError("Profile is already complete")

        user.display_name = profile.name
        await self._user_repo.update(user)

        assignment_count = await self._offering_repo.count_active_assignments_for_teacher(user.id)
        logger.info(
            "teacher_profile_completed",
            user_id=user.id,
            assignment_count=assignment_count,
        )
        return derive_onboarding_state(
            profile=profile,
            assignment_count=assignment_count,
            account_status=user.status,
            teacher_capacity=user.teacher_capacity,
        )

    async def update_capacity(
        self,
        payload: TeacherCapacityUpdate,
        claims: dict[str, object],
    ) -> TeacherCapacityUpdateRead:
        user = await self._require_teacher(claims)
        if user.status == UserAccountStatus.SUSPENDED:
            raise PermissionDeniedError("Suspended teachers cannot update capacity")

        assignment_count = await self._offering_repo.count_active_assignments_for_teacher(user.id)
        old_capacity = user.teacher_capacity or DEFAULT_TEACHER_CAPACITY
        new_capacity = payload.teacher_capacity
        flagged = new_capacity < assignment_count

        user.teacher_capacity = new_capacity
        await self._user_repo.update(user)

        await audit(
            session=self._session,
            action=CAPACITY_UPDATED,
            actor_id=str(claims.get("sub", "")),
            actor_role=user.role.value,
            target_type="user",
            target_id=user.id,
            school_id=user.school_id,
            metadata={
                "old_capacity": old_capacity,
                "new_capacity": new_capacity,
                "assignment_count": assignment_count,
                "flagged": flagged,
            },
        )

        params = {
            "teacher_name": user.display_name,
            "old_capacity": str(old_capacity),
            "new_capacity": str(new_capacity),
            "assignment_count": str(assignment_count),
        }
        await notify_account_event(
            session=self._session,
            template_key="account.capacity_changed",
            recipient_user_id=user.id,
            school_id=user.school_id or "",
            params=params,
            metadata={"flagged": flagged},
        )
        admins = await self._user_repo.list_by_school_and_role(
            user.school_id or "", UserRole.SCHOOL_ADMIN
        )
        for admin in admins:
            if admin.status != UserAccountStatus.ACTIVE:
                continue
            await notify_account_event(
                session=self._session,
                template_key="account.capacity_changed",
                recipient_user_id=admin.id,
                school_id=user.school_id or "",
                params={**params, "actor_name": user.display_name},
                metadata={"teacher_id": user.id, "flagged": flagged},
            )

        logger.info(
            "teacher_capacity_updated",
            user_id=user.id,
            old_capacity=old_capacity,
            new_capacity=new_capacity,
            flagged=flagged,
        )
        return TeacherCapacityUpdateRead(
            teacher_capacity=new_capacity,
            assignment_count=assignment_count,
            capacity_below_assignments=flagged,
        )

    async def list_subject_options(self, claims: dict[str, object]) -> list[Subject]:
        user = await self._require_teacher(claims)
        assert user.school_id is not None
        return await self._subject_repo.list_by_school(user.school_id, include_archived=False)
