"""Independent student onboarding business logic — T-071 / T-107."""

from __future__ import annotations

from datetime import date, datetime, timezone

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, PermissionDeniedError, PreconditionFailedError
from app.features.exam_syllabi.repository import ExamSyllabiRepository
from app.features.independent_student_onboarding.models import IndependentStudentProfile
from app.features.independent_student_onboarding.repository import (
    IndependentStudentProfileRepository,
)
from app.features.independent_student_onboarding.schemas import (
    ExamFrameworkOption,
    IndependentStudentExamDateUpdate,
    IndependentStudentOnboardingRead,
    IndependentStudentOnboardingState,
    IndependentStudentProfileComplete,
    IndependentStudentProfileRead,
)
from app.features.independent_users.models import (
    IndependentUser,
    IndependentUserAccountStatus,
    IndependentUserRole,
)
from app.features.independent_users.repository import IndependentUserRepository
from app.features.student_onboarding.exam_countdown import (
    EXAM_COUNTDOWN_DAYS,
    format_countdown_sent,
    future_date_warning,
    has_exam_passed_notified,
    mark_exam_passed_notified,
    parse_countdown_sent,
)

logger = structlog.get_logger(__name__)


def derive_independent_student_state(
    *,
    profile: IndependentStudentProfile | None,
    future_date_warning_msg: str | None = None,
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
    exam_date_passed = False
    if profile is not None:
        profile_read = IndependentStudentProfileRead.model_validate(profile)
        profile_read.diagnostic_available = True
        profile_read.diagnostic_deferred = True
        exam_date_passed = profile.exam_date is not None and profile.exam_date < date.today()
    return IndependentStudentOnboardingRead(
        state=state,
        profile_complete=profile_complete,
        ready_to_study=ready_to_study,
        self_study_only=True,
        exam_date_passed=exam_date_passed,
        future_date_warning=future_date_warning_msg,
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
            raise PermissionDeniedError(
                "Independent student onboarding only for independent students"
            )
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
        warning = future_date_warning(payload.exam_date)
        profile.exam_date = payload.exam_date
        profile.exam_countdown_sent_days = None
        profile.profile_completed_at = now
        profile = await self._profile_repo.update(profile)

        logger.info("independent_student_profile_completed", user_id=user.id)
        from app.features.diagnostics.notifications import (
            notify_diagnostic_available,
            safe_notify,
        )

        await safe_notify(
            notify_diagnostic_available(
                session=self._session,
                recipient_user_id=user.authentik_id,
                school_id=None,
                locale=profile.language_preference,
            )
        )
        return derive_independent_student_state(profile=profile, future_date_warning_msg=warning)

    async def set_exam_date(
        self,
        payload: IndependentStudentExamDateUpdate,
        claims: dict[str, object],
    ) -> IndependentStudentOnboardingRead:
        """Update exam date after profile complete (incl. EXAM_PASSED re-set) — T-107."""
        user = await self._require_independent_student(claims)
        if user.status == IndependentUserAccountStatus.SUSPENDED:
            raise PermissionDeniedError("Suspended students cannot update profile")

        profile = await self._profile_repo.get_by_user_id(user.id)
        if profile is None or profile.profile_completed_at is None:
            raise PreconditionFailedError("Complete profile before updating exam date")

        warning = future_date_warning(payload.exam_date)
        profile.exam_date = payload.exam_date
        profile.exam_countdown_sent_days = None
        profile = await self._profile_repo.update(profile)
        logger.info(
            "independent_student_exam_date_set", user_id=user.id, exam_date=payload.exam_date
        )
        return derive_independent_student_state(profile=profile, future_date_warning_msg=warning)

    async def send_exam_countdown_notifications(self) -> int:
        """Fire countdown + exam-passed notifications for independent students (T-107)."""
        from app.infrastructure.notifications.self_study import notify_self_study_event

        today = date.today()
        count = 0
        profiles = await self._profile_repo.list_with_exam_dates()
        for profile in profiles:
            if profile.exam_date is None:
                continue
            days_until = (profile.exam_date - today).days
            user = await self._user_repo.get_by_id(profile.user_id)
            if user is None or user.deleted_at is not None:
                continue

            if days_until < 0:
                if has_exam_passed_notified(profile.exam_countdown_sent_days):
                    continue
                await notify_self_study_event(
                    session=self._session,
                    template_key="self_study.exam_passed",
                    recipient_user_id=user.authentik_id,
                    school_id=None,
                    locale=profile.language_preference,
                    params={"exam_date": profile.exam_date.isoformat()},
                    metadata={"exam_date": profile.exam_date.isoformat(), "event": "exam_passed"},
                )
                profile.exam_countdown_sent_days = mark_exam_passed_notified(
                    profile.exam_countdown_sent_days
                )
                await self._profile_repo.update(profile)
                count += 1
                continue

            if days_until not in EXAM_COUNTDOWN_DAYS:
                continue

            sent = parse_countdown_sent(profile.exam_countdown_sent_days)
            if days_until in sent:
                continue

            await notify_self_study_event(
                session=self._session,
                template_key="self_study.exam_countdown",
                recipient_user_id=user.authentik_id,
                school_id=None,
                locale=profile.language_preference,
                params={
                    "days_remaining": str(days_until),
                    "exam_date": profile.exam_date.isoformat(),
                },
                metadata={
                    "days_remaining": days_until,
                    "exam_date": profile.exam_date.isoformat(),
                },
            )
            sent.add(days_until)
            passed = has_exam_passed_notified(profile.exam_countdown_sent_days)
            profile.exam_countdown_sent_days = format_countdown_sent(sent, passed=passed)
            await self._profile_repo.update(profile)
            count += 1
            logger.info(
                "independent_exam_countdown_notification_sent",
                user_id=user.id,
                days_remaining=days_until,
            )
        return count
