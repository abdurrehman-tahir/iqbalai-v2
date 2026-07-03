"""Graduation and auto-migration business logic — T-085/T-086."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.exceptions import (
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    PreconditionFailedError,
)
from app.features.exam_syllabi.repository import ExamSyllabiRepository
from app.features.grades.models import Grade
from app.features.grades.scope import assert_grade_in_scope
from app.features.graduation.models import (
    GraduationMigrationLog,
    GraduationMigrationStatus,
    GraduationRequest,
    GraduationRequestStatus,
)
from app.features.graduation.repository import (
    GraduationMigrationLogRepository,
    GraduationRequestRepository,
)
from app.features.graduation.schemas import GraduationRequestRead, StudentGraduationStatusRead
from app.features.independent_student_onboarding.models import IndependentStudentProfile
from app.features.independent_student_onboarding.repository import (
    IndependentStudentProfileRepository,
)
from app.features.independent_users.models import (
    IndependentUser,
    IndependentUserAccountStatus,
    IndependentUserRole,
)
from app.features.independent_users.repository import IndependentUserRepository
from app.features.parent_child_links.models import ParentChildLinkStatus
from app.features.parent_child_links.repository import ParentChildLinkRepository
from app.features.student_enrollments.models import StudentEnrollment, StudentEnrollmentStatus
from app.features.student_enrollments.repository import StudentEnrollmentRepository
from app.features.student_onboarding.models import StudentProfile
from app.features.student_onboarding.repository import StudentProfileRepository
from app.features.users.models import UserRole
from app.features.users.repository import UserRepository
from app.infrastructure.audit.log import audit
from app.infrastructure.authentik.client import AuthentikClientProtocol, get_authentik_client
from app.infrastructure.events.graduation import publish_graduation_event
from app.infrastructure.notifications.account import notify_account_event

logger = structlog.get_logger(__name__)

GRADUATION_STUDENT_MESSAGE = (
    "You've graduated! For 6 months you can still use Self-Study mode in your school account. "
    "After that, your account will move to Independent mode with the same email and password."
)
MIGRATION_REMINDER_DAYS = (30, 7)


def _parse_sent_days(raw: str | None) -> set[int]:
    if not raw:
        return set()
    return {int(part) for part in raw.split(",") if part.strip().isdigit()}


def _format_sent_days(sent: set[int]) -> str | None:
    return ",".join(str(day) for day in sorted(sent)) if sent else None


class GraduationService:
    def __init__(
        self,
        session: AsyncSession,
        authentik: AuthentikClientProtocol | None = None,
    ) -> None:
        self._session = session
        self._requests = GraduationRequestRepository(session)
        self._migration_logs = GraduationMigrationLogRepository(session)
        self._users = UserRepository(session)
        self._profiles = StudentProfileRepository(session)
        self._enrollments = StudentEnrollmentRepository(session)
        self._links = ParentChildLinkRepository(session)
        self._independent_users = IndependentUserRepository(session)
        self._independent_profiles = IndependentStudentProfileRepository(session)
        self._syllabi = ExamSyllabiRepository(session)
        self._authentik = authentik or get_authentik_client()

    async def _get_grade(self, grade_id: str) -> Grade:
        from sqlalchemy import select

        from app.db.base import not_deleted

        result = await self._session.execute(
            select(Grade).where(Grade.id == grade_id, not_deleted(Grade))
        )
        grade = result.scalar_one_or_none()
        if grade is None:
            raise NotFoundError("Grade not found")
        return grade

    async def _active_enrollment(self, student_user_id: str) -> StudentEnrollment | None:
        enrollments = await self._enrollments.list_for_student(student_user_id)
        for enrollment in enrollments:
            if enrollment.status in {
                StudentEnrollmentStatus.ACTIVE,
                StudentEnrollmentStatus.GRADUATED,
            }:
                return enrollment
        return None

    async def _assert_final_grade(self, enrollment: StudentEnrollment) -> None:
        settings = get_settings()
        grade = await self._get_grade(enrollment.grade_id)
        if grade.level_ordinal < settings.FINAL_GRADE_LEVEL_ORDINAL:
            raise PreconditionFailedError(
                "Student must be enrolled in a final grade before graduation"
            )

    def build_student_graduation_status(
        self,
        *,
        profile: StudentProfile | None,
        migration_log: GraduationMigrationLog | None,
        pending_request: GraduationRequest | None = None,
    ) -> StudentGraduationStatusRead:
        if profile is None or not profile.is_graduated or profile.migrated_out:
            return StudentGraduationStatusRead(
                is_graduated=profile.is_graduated if profile else False,
                migrated_out=profile.migrated_out if profile else False,
                pending_graduation_request=(
                    GraduationRequestRead.model_validate(pending_request)
                    if pending_request
                    else None
                ),
            )

        self_study = profile.self_study_mode_enabled if profile else True
        scheduled = migration_log.migration_scheduled_at if migration_log else None
        return StudentGraduationStatusRead(
            is_graduated=True,
            school_read_only=True,
            lecture_read_only=True,
            self_study_enabled=self_study,
            migrated_out=False,
            graduated_at=profile.graduated_at,
            migration_scheduled_at=scheduled,
            graduation_message=GRADUATION_STUDENT_MESSAGE,
            pending_graduation_request=None,
        )

    async def get_student_graduation_status(
        self, claims: dict[str, object]
    ) -> StudentGraduationStatusRead:
        user = await self._users.get_by_authentik_id(str(claims.get("sub", "")))
        if user is None or user.role != UserRole.STUDENT:
            raise PermissionDeniedError()
        profile = await self._profiles.get_by_user_id(user.id)
        migration_log = await self._migration_logs.get_by_student(user.id)
        pending = await self._requests.get_pending_for_student(user.id)
        return self.build_student_graduation_status(
            profile=profile,
            migration_log=migration_log,
            pending_request=pending,
        )

    async def create_graduation_request(
        self,
        payload_student_user_id: str,
        claims: dict[str, object],
        actor_id: str,
    ) -> GraduationRequestRead:
        actor = await self._users.get_by_authentik_id(actor_id)
        if actor is None or actor.role != UserRole.COORDINATOR:
            raise PermissionDeniedError()

        student = await self._users.get_by_id(payload_student_user_id)
        if (
            student is None
            or student.role != UserRole.STUDENT
            or student.school_id != actor.school_id
        ):
            raise NotFoundError("Student not found")

        enrollment = await self._active_enrollment(student.id)
        if enrollment is None:
            raise PreconditionFailedError("Student has no active enrollment")
        await self._assert_final_grade(enrollment)
        grade = await self._get_grade(enrollment.grade_id)
        assert_grade_in_scope(actor, grade.name)

        profile = await self._profiles.get_by_user_id(student.id)
        if profile is not None and profile.is_graduated:
            raise ConflictError("Student is already graduated")

        pending = await self._requests.get_pending_for_student(student.id)
        if pending is not None:
            raise ConflictError("A graduation request is already pending approval")

        now = datetime.now(timezone.utc)
        request = GraduationRequest(
            student_user_id=student.id,
            school_id=student.school_id or actor.school_id or "",
            requested_by_user_id=actor.id,
            status=GraduationRequestStatus.PENDING,
            requested_at=now,
        )
        await self._requests.create(request)
        await self._session.commit()

        await audit(
            session=self._session,
            action="graduation.requested",
            actor_id=actor_id,
            actor_role=actor.role.value,
            target_type="graduation_request",
            target_id=request.id,
            school_id=student.school_id,
            metadata={"student_user_id": student.id},
        )
        return GraduationRequestRead.model_validate(request)

    async def approve_graduation_request(
        self,
        request_id: str,
        claims: dict[str, object],
        actor_id: str,
    ) -> GraduationRequestRead:
        actor = await self._users.get_by_authentik_id(actor_id)
        if actor is None or actor.role != UserRole.SCHOOL_ADMIN:
            raise PermissionDeniedError()

        request = await self._requests.get_by_id(request_id)
        if request is None or request.school_id != actor.school_id:
            raise NotFoundError("Graduation request not found")
        if request.status != GraduationRequestStatus.PENDING:
            raise PreconditionFailedError("Graduation request is not pending")

        now = datetime.now(timezone.utc)
        request.status = GraduationRequestStatus.APPROVED
        request.approved_by_user_id = actor.id
        request.approved_at = now
        await self._requests.update(request)

        student = await self._users.get_by_id(request.student_user_id)
        if student is None:
            raise NotFoundError("Student not found")

        profile = await self._profiles.get_by_user_id(student.id)
        if profile is None:
            raise PreconditionFailedError("Student profile not found")

        enrollment = await self._active_enrollment(student.id)
        if enrollment is None:
            raise PreconditionFailedError("Student enrollment not found")

        profile.is_graduated = True
        profile.graduated_at = now
        await self._profiles.update(profile)

        enrollment.status = StudentEnrollmentStatus.GRADUATED
        await self._enrollments.update(enrollment)

        settings = get_settings()
        migration_log = GraduationMigrationLog(
            student_user_id=student.id,
            graduated_at=now,
            migration_scheduled_at=now + timedelta(days=settings.GRADUATION_GRACE_DAYS),
            migration_status=GraduationMigrationStatus.PENDING,
        )
        await self._migration_logs.create(migration_log)
        await self._session.commit()

        await audit(
            session=self._session,
            action="graduation.approved",
            actor_id=actor_id,
            actor_role=actor.role.value,
            target_type="graduation_request",
            target_id=request.id,
            school_id=student.school_id,
            metadata={
                "student_user_id": student.id,
                "migration_scheduled_at": migration_log.migration_scheduled_at.isoformat(),
            },
        )

        await notify_account_event(
            session=self._session,
            template_key="account.graduated",
            locale=profile.language_preference,
            recipient_user_id=student.authentik_id,
            recipient_email=student.email,
            school_id=student.school_id,
            params={"name": student.display_name},
        )
        await publish_graduation_event(
            event_type="student.graduated",
            payload={"student_user_id": student.id, "school_id": student.school_id},
        )
        logger.info("student_graduated", student_user_id=student.id)
        return GraduationRequestRead.model_validate(request)

    async def list_graduation_requests(
        self, claims: dict[str, object]
    ) -> list[GraduationRequestRead]:
        actor = await self._users.get_by_authentik_id(str(claims.get("sub", "")))
        if actor is None or actor.school_id is None:
            raise PermissionDeniedError()
        if actor.role not in {UserRole.COORDINATOR, UserRole.SCHOOL_ADMIN}:
            raise PermissionDeniedError()
        rows = await self._requests.list_for_school(actor.school_id)
        return [GraduationRequestRead.model_validate(row) for row in rows]

    async def migrate_eligible_students(self) -> int:
        settings = get_settings()
        now = datetime.now(timezone.utc)
        due = await self._migration_logs.list_due_for_migration(now)
        count = 0
        for log in due:
            if log.migration_attempts >= settings.GRADUATION_MIGRATION_MAX_ATTEMPTS:
                continue
            success = await self._migrate_student(log)
            if success:
                count += 1
        return count

    async def _migrate_student(self, log: GraduationMigrationLog) -> bool:
        settings = get_settings()
        log.migration_status = GraduationMigrationStatus.IN_PROGRESS
        log.migration_attempts += 1
        await self._migration_logs.update(log)
        await self._session.commit()

        try:
            student = await self._users.get_by_id(log.student_user_id)
            profile = await self._profiles.get_by_user_id(log.student_user_id)
            if student is None or profile is None:
                raise NotFoundError("Student not found for migration")
            if profile.migrated_out:
                log.migration_status = GraduationMigrationStatus.SUCCEEDED
                log.migrated_at = profile.migrated_at or datetime.now(timezone.utc)
                await self._migration_logs.update(log)
                await self._session.commit()
                return True

            enrollment = await self._active_enrollment(student.id)
            grade_level = 12
            if enrollment is not None:
                grade = await self._get_grade(enrollment.grade_id)
                grade_level = grade.level_ordinal

            syllabi = await self._syllabi.list_syllabi()
            active_syllabi = [s for s in syllabi if s.deleted_at is None and s.is_active]
            if not active_syllabi:
                raise PreconditionFailedError("No active exam syllabus available for migration")
            syllabus_id = active_syllabi[0].id

            existing = await self._independent_users.get_by_authentik_id(student.authentik_id)
            if existing is None:
                independent_user = IndependentUser(
                    authentik_id=student.authentik_id,
                    email=student.email,
                    display_name=student.display_name,
                    role=IndependentUserRole.INDEPENDENT_STUDENT,
                    status=IndependentUserAccountStatus.ACTIVE,
                    language_preference=profile.language_preference,
                )
                self._session.add(independent_user)
                await self._session.flush()
            else:
                independent_user = existing

            ind_profile = await self._independent_profiles.get_by_user_id(independent_user.id)
            if ind_profile is None:
                ind_profile = IndependentStudentProfile(
                    user_id=independent_user.id,
                    name=profile.display_name,
                    language_preference=profile.language_preference,
                    grade_level=grade_level,
                    exam_syllabus_id=syllabus_id,
                    exam_date=profile.exam_date,
                    profile_completed_at=profile.profile_basic_completed_at,
                )
                self._session.add(ind_profile)
                await self._session.flush()

            links = await self._links.list_for_student(student.id)
            for link in links:
                if link.status == ParentChildLinkStatus.APPROVED:
                    link.status = ParentChildLinkStatus.REVOKED
                    link.revoked_at = datetime.now(timezone.utc)
                    await self._links.update(link)

            now = datetime.now(timezone.utc)
            profile.migrated_out = True
            profile.migrated_at = now
            await self._profiles.update(profile)

            log.migration_status = GraduationMigrationStatus.SUCCEEDED
            log.migrated_at = now
            log.last_error = None
            await self._migration_logs.update(log)
            await self._session.commit()

            await self._authentik.set_tenant_type(student.authentik_id, "independent")

            await audit(
                session=self._session,
                action="graduation.migrated",
                actor_id="system",
                actor_role="system",
                target_type="student_profile",
                target_id=student.id,
                school_id=student.school_id,
                metadata={"flagged": True, "independent_user_id": independent_user.id},
            )
            await notify_account_event(
                session=self._session,
                template_key="account.migration_complete",
                locale=profile.language_preference,
                recipient_user_id=student.authentik_id,
                recipient_email=student.email,
                school_id=student.school_id,
                params={"name": student.display_name},
            )
            await publish_graduation_event(
                event_type="student.migrated_to_independent",
                payload={"student_user_id": student.id, "independent_user_id": independent_user.id},
            )
            logger.info("student_migrated_to_independent", student_user_id=student.id)
            return True
        except Exception as exc:
            await self._session.rollback()
            log = await self._migration_logs.get_by_student(log.student_user_id)
            if log is None:
                return False
            log.migration_status = GraduationMigrationStatus.FAILED
            log.last_error = str(exc)[:2000]
            await self._migration_logs.update(log)
            await self._session.commit()

            if log.migration_attempts >= settings.GRADUATION_MIGRATION_MAX_ATTEMPTS:
                from app.infrastructure.celery.dlq import push_task_dlq

                push_task_dlq(
                    "graduation.migrate_eligible_students",
                    {"student_user_id": log.student_user_id},
                    log.last_error or "max attempts exceeded",
                )
                await audit(
                    session=self._session,
                    action="graduation.migration_failed",
                    actor_id="system",
                    actor_role="system",
                    target_type="graduation_migration_log",
                    target_id=log.id,
                    metadata={"flagged": True, "attempts": log.migration_attempts},
                )
            logger.error(
                "student_migration_failed",
                student_user_id=log.student_user_id,
                error=str(exc),
                attempts=log.migration_attempts,
            )
            return False

    async def send_migration_reminders(self) -> int:
        today = datetime.now(timezone.utc).date()
        count = 0
        logs = await self._migration_logs.list_pending_reminders()
        for log in logs:
            profile = await self._profiles.get_by_user_id(log.student_user_id)
            student = await self._users.get_by_id(log.student_user_id)
            if profile is None or student is None or profile.migrated_out:
                continue
            days_until = (log.migration_scheduled_at.date() - today).days
            if days_until not in MIGRATION_REMINDER_DAYS:
                continue
            sent = _parse_sent_days(profile.migration_reminder_sent_days)
            if days_until in sent:
                continue

            template = (
                "account.migration_reminder_30"
                if days_until == 30
                else "account.migration_reminder_7"
            )
            await notify_account_event(
                session=self._session,
                template_key=template,
                locale=profile.language_preference,
                recipient_user_id=student.authentik_id,
                recipient_email=student.email,
                school_id=student.school_id,
                params={
                    "name": student.display_name,
                    "days_remaining": str(days_until),
                    "migration_date": log.migration_scheduled_at.date().isoformat(),
                },
            )
            sent.add(days_until)
            profile.migration_reminder_sent_days = _format_sent_days(sent)
            await self._profiles.update(profile)
            await self._session.commit()
            count += 1
        return count
