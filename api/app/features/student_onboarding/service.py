"""School student onboarding business logic — T-078."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    NotFoundError,
    PermissionDeniedError,
    PreconditionFailedError,
    ValidationError,
)
from app.features.student_enrollments.models import StudentEnrollment, StudentEnrollmentStatus
from app.features.student_onboarding.models import StudentProfile
from app.features.student_onboarding.repository import StudentProfileRepository
from app.features.student_onboarding.schemas import (
    SchoolStudentOnboardingRead,
    SchoolStudentOnboardingState,
    StudentExamDateUpdate,
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
EXAM_DATE_MAX_YEARS = 5
EXAM_COUNTDOWN_DAYS = (30, 14, 7, 1)
FUTURE_DATE_WARNING = (
    "Exam date is more than 5 years away — you can update it anytime before your exam"
)


def _future_date_warning(exam_date: date) -> str | None:
    if exam_date > date.today() + timedelta(days=365 * EXAM_DATE_MAX_YEARS):
        return FUTURE_DATE_WARNING
    return None


def _parse_countdown_sent(raw: str | None) -> set[int]:
    if not raw:
        return set()
    sent: set[int] = set()
    for part in raw.split(","):
        part = part.strip()
        if part.isdigit():
            sent.add(int(part))
    return sent


def _format_countdown_sent(sent: set[int]) -> str | None:
    if not sent:
        return None
    return ",".join(str(day) for day in sorted(sent))


def derive_school_student_state(
    *,
    user: User,
    profile: StudentProfile | None,
    enrollment_grade_id: str | None,
    migration_scheduled_at: datetime | None = None,
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

    if profile is not None and profile.is_graduated and not profile.migrated_out:
        self_study = profile.self_study_mode_enabled
        return SchoolStudentOnboardingRead(
            state=SchoolStudentOnboardingState.SCHOOL_READ_ONLY,
            profile_basic_complete=True,
            mode_selected=True,
            ready_to_study=False,
            show_complete_profile_banner=False,
            exam_date_set=profile.exam_date is not None,
            enrollment_grade_id=enrollment_grade_id,
            profile=StudentProfileRead.model_validate(profile),
            school_read_only=True,
            lecture_read_only=True,
            self_study_enabled=self_study,
            graduation_message=(
                "You've graduated! For 6 months you can still use Self-Study mode in your "
                "school account. After that, your account will move to Independent mode."
            ),
            migration_scheduled_at=migration_scheduled_at,
        )

    profile_basic_complete = profile is not None and profile.profile_basic_completed_at is not None
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
    exam_date_set = profile is not None and profile.exam_date is not None
    show_banner = (
        ready_to_study
        and profile is not None
        and (not profile.deferrable_banner_dismissed and not exam_date_set)
    )

    return SchoolStudentOnboardingRead(
        state=state,
        profile_basic_complete=profile_basic_complete,
        mode_selected=mode_selected,
        ready_to_study=ready_to_study,
        show_complete_profile_banner=show_banner,
        exam_date_set=exam_date_set,
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
        migration_scheduled_at = None
        if profile is not None and profile.is_graduated:
            from app.features.graduation.repository import GraduationMigrationLogRepository

            log = await GraduationMigrationLogRepository(self._session).get_by_student(user.id)
            if log is not None:
                migration_scheduled_at = log.migration_scheduled_at
        return derive_school_student_state(
            user=user,
            profile=profile,
            enrollment_grade_id=grade_id,
            migration_scheduled_at=migration_scheduled_at,
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

        # T-101: seed user_settings so the Mode Switcher has an active mode immediately.
        from app.features.student_mode.service import StudentModeService

        await StudentModeService(self._session).ensure_settings_for_onboarding(
            user_id=user.id,
            lecture_mode=payload.lecture_mode,
            self_study_mode=payload.self_study_mode,
        )

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
        if profile is None or not (profile.lecture_mode_enabled or profile.self_study_mode_enabled):
            raise PreconditionFailedError("Complete onboarding before dismissing the banner")

        profile.deferrable_banner_dismissed = True
        profile = await self._profile_repo.update(profile)
        grade_id = await self._active_enrollment_grade_id(user.id)
        return derive_school_student_state(user=user, profile=profile, enrollment_grade_id=grade_id)

    async def set_exam_date(
        self,
        payload: StudentExamDateUpdate,
        claims: dict[str, object],
        actor_id: str,
    ) -> SchoolStudentOnboardingRead:
        user = await self._require_student(claims)
        profile = await self._profile_repo.get_by_user_id(user.id)
        if profile is None or not (profile.lecture_mode_enabled or profile.self_study_mode_enabled):
            raise PreconditionFailedError("Complete onboarding before setting an exam date")

        warning = _future_date_warning(payload.exam_date)
        profile.exam_date = payload.exam_date
        profile.exam_countdown_sent_days = None
        profile = await self._profile_repo.update(profile)

        await audit(
            session=self._session,
            action="student.exam_date_set",
            actor_id=actor_id,
            target_type="student_profile",
            target_id=user.id,
            school_id=user.school_id,
            metadata={"exam_date": payload.exam_date.isoformat()},
        )
        logger.info("school_student_exam_date_set", user_id=user.id, exam_date=payload.exam_date)

        state = derive_school_student_state(
            user=user,
            profile=profile,
            enrollment_grade_id=await self._active_enrollment_grade_id(user.id),
        )
        if warning:
            return state.model_copy(update={"future_date_warning": warning})
        return state

    async def send_exam_countdown_notifications(self) -> int:
        """Fire 30/14/7/1-day countdown notifications for school students."""
        from app.infrastructure.notifications.self_study import notify_self_study_event

        today = date.today()
        count = 0
        profiles = await self._profile_repo.list_with_exam_dates()
        for profile in profiles:
            if profile.exam_date is None:
                continue
            days_until = (profile.exam_date - today).days
            if days_until not in EXAM_COUNTDOWN_DAYS:
                continue

            sent = _parse_countdown_sent(profile.exam_countdown_sent_days)
            if days_until in sent:
                continue

            user = await self._user_repo.get_by_id(profile.user_id)
            if user is None or user.deleted_at is not None:
                continue

            await notify_self_study_event(
                session=self._session,
                template_key="self_study.exam_countdown",
                recipient_user_id=user.authentik_id,
                school_id=user.school_id,
                locale=profile.language_preference,
                params={
                    "days_remaining": str(days_until),
                    "exam_date": profile.exam_date.isoformat(),
                },
                metadata={"days_remaining": days_until, "exam_date": profile.exam_date.isoformat()},
            )
            sent.add(days_until)
            profile.exam_countdown_sent_days = _format_countdown_sent(sent)
            await self._profile_repo.update(profile)
            count += 1
            logger.info(
                "exam_countdown_notification_sent",
                user_id=user.id,
                days_remaining=days_until,
            )
        return count
