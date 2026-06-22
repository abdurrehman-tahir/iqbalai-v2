"""School student onboarding business logic — T-078."""

from __future__ import annotations

from datetime import datetime, timezone

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, PermissionDeniedError, PreconditionFailedError, ValidationError
from app.features.student_enrollments.models import StudentEnrollment, StudentEnrollmentStatus
from app.features.student_onboarding.models import StudentProfile
from app.features.student_onboarding.repository import StudentProfileRepository
from app.features.student_onboarding.schemas import (
    SchoolStudentOnboardingRead,
    SchoolStudentOnboardingState,
    StudentModeSelect,
    StudentProfileBasicComplete,
    StudentProfileRead,
)
from app.features.tos.service import TosService
from app.features.users.models import User, UserAccountStatus, UserRole
from app.features.users.repository import UserRepository
from app.infrastructure.audit.log import audit

logger = structlog.get_logger(__name__)

SUPPORTED_LANGUAGES = frozenset({"en", "ur", "sd", "ps"})


def derive_school_student_state(
    *,
    user: User,
    profile: StudentProfile | None,
    enrollment_grade_id: str | None,
) -> SchoolStudentOnboardingRead:
    if user.status == UserAccountStatus.INVITED:
        return SchoolStudentOnboardingRead(
            state=SchoolStudentOnboardingState.INVITED,
            profile_basic_complete=False,
            mode_selected=False,
            ready_to_study=False,
            show_complete_profile_banner=False,
            enrollment_grade_id=enrollment_grade_id,
            profile=None,
        )

    profile_basic_complete = (
        profile is not None and profile.profile_basic_completed_at is not None
    )
    mode_selected = (
        profile is not None
        and profile.profile_basic_completed_at is not None
        and (profile.lecture_mode_enabled or profile.self_study_mode_enabled)
    )
    ready_to_study = mode_selected

    if not profile_basic_complete:
        state = SchoolStudentOnboardingState.PROFILE_BASIC
    elif not mode_selected:
        state = SchoolStudentOnboardingState.MODE_SELECTION
    else:
        state = SchoolStudentOnboardingState.READY_TO_STUDY

    profile_read = StudentProfileRead.model_validate(profile) if profile else None
    show_banner = ready_to_study and (
        profile is None or not profile.deferrable_banner_dismissed
    )

    return SchoolStudentOnboardingRead(
        state=state,
        profile_basic_complete=profile_basic_complete,
        mode_selected=mode_selected,
        ready_to_study=ready_to_study,
        show_complete_profile_banner=show_banner,
        enrollment_grade_id=enrollment_grade_id,
        profile=profile_read,
    )


class StudentOnboardingService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._profile_repo = StudentProfileRepository(session)
        self._user_repo = UserRepository(session)
        self._tos = TosService(session)

    async def _require_student(self, claims: dict[str, object]) -> User:
        user = await self._user_repo.get_by_authentik_id(str(claims.get("sub", "")))
        if user is None or user.deleted_at is not None:
            raise NotFoundError("User profile not found")
        if user.role != UserRole.STUDENT:
            raise PermissionDeniedError("School student onboarding is only for students")
        if user.school_id is None:
            raise PermissionDeniedError("Student must belong to a school")
        return user

    async def _active_enrollment_grade_id(self, user_id: str) -> str | None:
        # Latest active enrollment — grade is auto-satisfied from T-077 enrollment.
        from sqlalchemy import select

        from app.features.student_enrollments.models import StudentEnrollment
        from app.db.base import not_deleted

        result = await self._session.execute(
            select(StudentEnrollment)
            .where(
                StudentEnrollment.student_user_id == user_id,
                StudentEnrollment.status == StudentEnrollmentStatus.ACTIVE,
                not_deleted(StudentEnrollment),
            )
            .order_by(StudentEnrollment.enrolled_at.desc())
            .limit(1)
        )
        row = result.scalar_one_or_none()
        return row.grade_id if row else None

    async def get_onboarding_state(self, claims: dict[str, object]) -> SchoolStudentOnboardingRead:
        user = await self._require_student(claims)
        profile = await self._profile_repo.get_by_user_id(user.id)
        grade_id = await self._active_enrollment_grade_id(user.id)
        return derive_school_student_state(
            user=user, profile=profile, enrollment_grade_id=grade_id
        )

    async def complete_profile_basic(
        self,
        payload: StudentProfileBasicComplete,
        claims: dict[str, object],
        actor_id: str,
        ip_address: str | None = None,
    ) -> SchoolStudentOnboardingRead:
        user = await self._require_student(claims)
        if user.status == UserAccountStatus.INVITED:
            raise PreconditionFailedError("Accept your invite and set a password before onboarding")
        if user.status == UserAccountStatus.SUSPENDED:
            raise PermissionDeniedError("Suspended students cannot complete onboarding")
        if payload.language_preference not in SUPPORTED_LANGUAGES:
            raise ValidationError(f"Unsupported language '{payload.language_preference}'")

        profile = await self._profile_repo.get_by_user_id(user.id)
        if profile is not None and profile.profile_basic_completed_at is not None:
            raise PreconditionFailedError("Profile basics are already complete")

        await self._tos.accept_tos(user.id, payload.tos_version_id, ip_address)
        now = datetime.now(timezone.utc)

        if profile is None:
            profile = StudentProfile(
                user_id=user.id,
                display_name=payload.display_name,
                language_preference=payload.language_preference,
                tos_accepted_at=now,
                profile_basic_completed_at=now,
            )
            profile = await self._profile_repo.create(profile)
        else:
            profile.display_name = payload.display_name
            profile.language_preference = payload.language_preference
            profile.tos_accepted_at = now
            profile.profile_basic_completed_at = now
            profile = await self._profile_repo.update(profile)

        user.display_name = payload.display_name
        await self._user_repo.update(user)

        await audit(
            session=self._session,
            action="student.profile_basic_completed",
            actor_id=actor_id,
            target_type="student_profile",
            target_id=user.id,
            school_id=user.school_id,
            metadata={"language": payload.language_preference},
        )
        grade_id = await self._active_enrollment_grade_id(user.id)
        return derive_school_student_state(user=user, profile=profile, enrollment_grade_id=grade_id)

    async def select_modes(
        self,
        payload: StudentModeSelect,
        claims: dict[str, object],
        actor_id: str,
    ) -> SchoolStudentOnboardingRead:
        user = await self._require_student(claims)
        profile = await self._profile_repo.get_by_user_id(user.id)
        if profile is None or profile.profile_basic_completed_at is None:
            raise PreconditionFailedError("Complete profile basics before selecting a mode")

        if profile.lecture_mode_enabled or profile.self_study_mode_enabled:
            raise PreconditionFailedError("Study modes are already selected")

        profile.lecture_mode_enabled = payload.lecture_mode
        profile.self_study_mode_enabled = payload.self_study_mode
        profile = await self._profile_repo.update(profile)

        await audit(
            session=self._session,
            action="student.modes_selected",
            actor_id=actor_id,
            target_type="student_profile",
            target_id=user.id,
            school_id=user.school_id,
            metadata={
                "lecture_mode": payload.lecture_mode,
                "self_study_mode": payload.self_study_mode,
            },
        )
        logger.info("school_student_ready_to_study", user_id=user.id)
        grade_id = await self._active_enrollment_grade_id(user.id)
        return derive_school_student_state(user=user, profile=profile, enrollment_grade_id=grade_id)

    async def dismiss_profile_banner(
        self, claims: dict[str, object], actor_id: str
    ) -> SchoolStudentOnboardingRead:
        user = await self._require_student(claims)
        profile = await self._profile_repo.get_by_user_id(user.id)
        if profile is None or not (
            profile.lecture_mode_enabled or profile.self_study_mode_enabled
        ):
            raise PreconditionFailedError("Complete onboarding before dismissing the banner")

        profile.deferrable_banner_dismissed = True
        profile = await self._profile_repo.update(profile)
        grade_id = await self._active_enrollment_grade_id(user.id)
        return derive_school_student_state(user=user, profile=profile, enrollment_grade_id=grade_id)
