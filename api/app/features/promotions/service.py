"""Promotion service — initiate (T-251), approve (T-252), execute (T-253)."""

from __future__ import annotations

from datetime import datetime, timezone

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.dependencies import ROLE_HIERARCHY
from app.core.exceptions import (
    NotFoundError,
    PermissionDeniedError,
    PreconditionFailedError,
    ValidationError,
)
from app.features.grades.models import Grade, GradeStatus
from app.features.grades.repository import GradeRepository
from app.features.grades.scope import assert_grade_in_scope, derive_level_ordinal, parse_grade_scope
from app.features.promotions.models import GradePromotionRequest, GradePromotionRequestStatus
from app.features.promotions.repository import GradePromotionRequestRepository
from app.features.promotions.schemas import (
    GradePromotionRequestCreate,
    GradePromotionRequestRead,
    PromotionRosterStudentRead,
)
from app.features.sections.models import DEFAULT_INTERNAL_NAME, Section, SectionStatus
from app.features.sections.repository import SectionRepository
from app.features.student_enrollments.models import StudentEnrollment, StudentEnrollmentStatus
from app.features.student_enrollments.repository import StudentEnrollmentRepository
from app.features.users.models import User, UserRole
from app.features.users.repository import UserRepository
from app.infrastructure.audit.log import audit

logger = structlog.get_logger(__name__)

# Matches Celery max_retries on execute_promotion (T-253 / ARCH §6.21).
EXECUTE_MAX_RETRIES = 5


class PromotionService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._requests = GradePromotionRequestRepository(session)
        self._grades = GradeRepository(session)
        self._enrollments = StudentEnrollmentRepository(session)
        self._sections = SectionRepository(session)
        self._users = UserRepository(session)

    async def _resolve_actor(self, actor_id: str) -> User:
        actor = await self._users.get_by_authentik_id(actor_id)
        if actor is None:
            raise PermissionDeniedError()
        return actor

    async def _get_grade_in_school(self, grade_id: str, school_id: str | None) -> Grade:
        grade = await self._grades.get_by_id(grade_id)
        if (
            grade is None
            or grade.deleted_at is not None
            or school_id is None
            or grade.school_id != school_id
        ):
            raise NotFoundError("Grade not found")
        return grade

    def _assert_coordinator_grade_scope(self, actor: User, grade: Grade) -> None:
        """Out-of-scope Coordinator → 404 (ticket acceptance); admins bypass via scope helper."""
        caller_level = ROLE_HIERARCHY.get(actor.role.value, 0)
        if caller_level >= ROLE_HIERARCHY["school_admin"]:
            return
        if actor.role != UserRole.COORDINATOR:
            raise PermissionDeniedError()
        scope = parse_grade_scope(actor.scoped_ids)
        if grade.name not in scope:
            raise NotFoundError("Grade not found")
        # Keep assert_grade_in_scope as a second line of defense for admins already returned.
        try:
            assert_grade_in_scope(actor, grade.name)
        except PermissionDeniedError as exc:
            raise NotFoundError("Grade not found") from exc

    async def list_roster_for_promotion(
        self,
        grade_id: str,
        claims: dict[str, object],
        *,
        actor_id: str,
    ) -> list[PromotionRosterStudentRead]:
        actor = await self._resolve_actor(actor_id)
        grade = await self._get_grade_in_school(grade_id, actor.school_id)
        self._assert_coordinator_grade_scope(actor, grade)

        enrollments = await self._enrollments.list_active_for_grade(
            grade.id, grade.academic_session
        )
        roster: list[PromotionRosterStudentRead] = []
        for enrollment in enrollments:
            student = await self._users.get_by_id(enrollment.student_user_id)
            if student is None:
                continue
            roster.append(
                PromotionRosterStudentRead(
                    student_user_id=student.id,
                    display_name=student.display_name,
                    email=student.email,
                    enrollment_id=enrollment.id,
                    section_id=enrollment.section_id,
                )
            )
        return roster

    async def create_promotion_request(
        self,
        grade_id: str,
        payload: GradePromotionRequestCreate,
        claims: dict[str, object],
        *,
        actor_id: str,
    ) -> GradePromotionRequestRead:
        actor = await self._resolve_actor(actor_id)
        grade = await self._get_grade_in_school(grade_id, actor.school_id)
        self._assert_coordinator_grade_scope(actor, grade)

        pending = await self._requests.get_pending_for_grade(grade.id)
        if pending is not None:
            raise PreconditionFailedError(
                "A promotion request is already pending approval for this grade"
            )

        enrollments = await self._enrollments.list_active_for_grade(
            grade.id, grade.academic_session
        )
        enrolled_ids = {e.student_user_id for e in enrollments}
        exclusion = list(dict.fromkeys(payload.exclusion_list))  # stable unique
        unknown = [sid for sid in exclusion if sid not in enrolled_ids]
        if unknown:
            raise ValidationError(
                "exclusion_list contains students not enrolled in this grade: " + ", ".join(unknown)
            )

        now = datetime.now(timezone.utc)
        row = GradePromotionRequest(
            school_id=grade.school_id,
            initiating_grade_id=grade.id,
            target_academic_session=payload.target_academic_session.strip(),
            target_grade_name=payload.target_grade_name.strip(),
            initiated_by_coordinator_id=actor.id,
            exclusion_list_jsonb=exclusion,
            status=GradePromotionRequestStatus.PENDING_APPROVAL,
            requested_at=now,
        )
        await self._requests.create(row)

        await audit(
            session=self._session,
            action="promotion.requested",
            actor_id=actor_id,
            actor_role=actor.role.value,
            target_type="grade_promotion_request",
            target_id=row.id,
            school_id=grade.school_id,
            metadata={
                "initiating_grade_id": grade.id,
                "exclusion_count": len(exclusion),
                "target_academic_session": row.target_academic_session,
            },
        )
        await self._notify_promotion_requested(row)

        return GradePromotionRequestRead.model_validate(row)

    async def _notify_promotion_requested(self, row: GradePromotionRequest) -> None:
        """Hook for T-255 (account.promotion_pending_approval + NATS promotion.requested)."""
        logger.info(
            "promotion.requested_hook",
            request_id=row.id,
            school_id=row.school_id,
            grade_id=row.initiating_grade_id,
        )

    async def _enqueue_execute_promotion(self, request_id: str, school_id: str) -> None:
        """Enqueue Celery ``execute_promotion`` (T-253)."""
        from app.features.promotions.tasks import execute_promotion

        execute_promotion.delay(school_id=school_id, promotion_request_id=request_id)
        logger.info(
            "promotion.execute_enqueued",
            request_id=request_id,
            school_id=school_id,
        )

    def _assert_school_admin_or_higher(self, actor: User) -> None:
        level = ROLE_HIERARCHY.get(actor.role.value, 0)
        if level < ROLE_HIERARCHY["school_admin"]:
            raise PermissionDeniedError()

    async def _get_request_in_school(
        self, request_id: str, school_id: str | None
    ) -> GradePromotionRequest:
        row = await self._requests.get_by_id(request_id)
        if row is None or school_id is None or row.school_id != school_id:
            raise NotFoundError("Promotion request not found")
        return row

    async def list_promotion_requests(
        self,
        claims: dict[str, object],
        *,
        actor_id: str,
        status: GradePromotionRequestStatus | None = None,
    ) -> list[GradePromotionRequestRead]:
        actor = await self._resolve_actor(actor_id)
        self._assert_school_admin_or_higher(actor)
        if actor.school_id is None:
            raise NotFoundError("Promotion request not found")
        rows = await self._requests.list_for_school(actor.school_id, status=status)
        return [GradePromotionRequestRead.model_validate(r) for r in rows]

    async def get_promotion_request(
        self,
        request_id: str,
        claims: dict[str, object],
        *,
        actor_id: str,
    ) -> GradePromotionRequestRead:
        actor = await self._resolve_actor(actor_id)
        # Coordinator+ may view (§6.21); school scope enforced.
        level = ROLE_HIERARCHY.get(actor.role.value, 0)
        if level < ROLE_HIERARCHY["coordinator"]:
            raise PermissionDeniedError()
        row = await self._get_request_in_school(request_id, actor.school_id)
        if actor.role == UserRole.COORDINATOR:
            grade = await self._grades.get_by_id(row.initiating_grade_id)
            if grade is None:
                raise NotFoundError("Promotion request not found")
            self._assert_coordinator_grade_scope(actor, grade)
        return GradePromotionRequestRead.model_validate(row)

    async def approve_promotion_request(
        self,
        request_id: str,
        claims: dict[str, object],
        *,
        actor_id: str,
    ) -> GradePromotionRequestRead:
        actor = await self._resolve_actor(actor_id)
        self._assert_school_admin_or_higher(actor)
        row = await self._get_request_in_school(request_id, actor.school_id)
        if row.status != GradePromotionRequestStatus.PENDING_APPROVAL:
            raise PreconditionFailedError("Promotion request is not pending approval")

        now = datetime.now(timezone.utc)
        row.status = GradePromotionRequestStatus.APPROVED
        row.approved_at = now
        row.approved_by_user_id = actor.id
        await self._requests.update(row)

        await audit(
            session=self._session,
            action="promotion.approved",
            actor_id=actor_id,
            actor_role=actor.role.value,
            target_type="grade_promotion_request",
            target_id=row.id,
            school_id=row.school_id,
            metadata={"initiating_grade_id": row.initiating_grade_id},
        )
        await self._enqueue_execute_promotion(row.id, row.school_id)
        return GradePromotionRequestRead.model_validate(row)

    async def reject_promotion_request(
        self,
        request_id: str,
        claims: dict[str, object],
        *,
        actor_id: str,
        reason: str | None = None,
    ) -> GradePromotionRequestRead:
        actor = await self._resolve_actor(actor_id)
        self._assert_school_admin_or_higher(actor)
        row = await self._get_request_in_school(request_id, actor.school_id)
        if row.status != GradePromotionRequestStatus.PENDING_APPROVAL:
            raise PreconditionFailedError("Promotion request is not pending approval")

        row.status = GradePromotionRequestStatus.REJECTED
        row.rejection_reason = reason
        row.approved_by_user_id = actor.id
        row.approved_at = datetime.now(timezone.utc)
        await self._requests.update(row)

        await audit(
            session=self._session,
            action="promotion.rejected",
            actor_id=actor_id,
            actor_role=actor.role.value,
            target_type="grade_promotion_request",
            target_id=row.id,
            school_id=row.school_id,
            metadata={"reason": reason},
        )
        return GradePromotionRequestRead.model_validate(row)

    # --- T-253 execute -----------------------------------------------------------

    async def _default_section_id(self, grade_id: str) -> str:
        rows = await self._sections.list_by_grade(grade_id)
        default = next((s for s in rows if s.is_default_internal), None)
        if default is None:
            section = Section(
                grade_id=grade_id,
                name=DEFAULT_INTERNAL_NAME,
                is_default_internal=True,
                status=SectionStatus.ACTIVE,
            )
            self._session.add(section)
            await self._session.flush()
            return section.id
        return default.id

    async def _ensure_grade(
        self,
        *,
        school_id: str,
        name: str,
        academic_session: str,
        promoted_from_grade_id: str | None = None,
    ) -> Grade:
        existing = await self._grades.get_by_name_session(school_id, name, academic_session)
        if existing is not None and existing.deleted_at is None:
            if promoted_from_grade_id is not None and existing.promoted_from_grade_id is None:
                existing.promoted_from_grade_id = promoted_from_grade_id
                await self._session.flush()
            return existing

        grade = Grade(
            school_id=school_id,
            name=name,
            academic_session=academic_session,
            level_ordinal=derive_level_ordinal(name),
            promoted_from_grade_id=promoted_from_grade_id,
            status=GradeStatus.ACTIVE,
        )
        self._session.add(grade)
        await self._session.flush()
        await self._default_section_id(grade.id)
        return grade

    async def _repoint_enrollment(
        self,
        enrollment: StudentEnrollment,
        *,
        target_grade: Grade,
    ) -> None:
        """Withdraw old enrollment and create a fresh active one on the target grade."""
        now = datetime.now(timezone.utc)
        enrollment.status = StudentEnrollmentStatus.WITHDRAWN
        section_id = await self._default_section_id(target_grade.id)
        new_enrollment = StudentEnrollment(
            school_id=enrollment.school_id,
            student_user_id=enrollment.student_user_id,
            grade_id=target_grade.id,
            section_id=section_id,
            academic_session=target_grade.academic_session,
            status=StudentEnrollmentStatus.ACTIVE,
            enrolled_at=now,
        )
        self._session.add(new_enrollment)
        await self._session.flush()

    async def execute_promotion_request(
        self,
        promotion_request_id: str,
        *,
        school_id: str,
    ) -> dict[str, object]:
        """Atomic mid-grade promotion execution (T-253). Final-grade → T-256."""
        row = await self._requests.get_by_id(promotion_request_id)
        if row is None or row.school_id != school_id:
            raise NotFoundError("Promotion request not found")
        if row.status not in {
            GradePromotionRequestStatus.APPROVED,
            GradePromotionRequestStatus.EXECUTING,
        }:
            raise PreconditionFailedError(
                f"Promotion request status {row.status.value} is not executable"
            )

        source = await self._grades.get_by_id(row.initiating_grade_id)
        if source is None or source.deleted_at is not None:
            raise NotFoundError("Initiating grade not found")

        settings = get_settings()
        if source.level_ordinal >= settings.FINAL_GRADE_LEVEL_ORDINAL:
            # Grade 12 / final cascade owned by T-256 — leave approved for that ticket.
            logger.info(
                "promotion.final_grade_deferred",
                request_id=row.id,
                level_ordinal=source.level_ordinal,
            )
            return {
                "request_id": row.id,
                "deferred_final_grade": True,
                "promoted_count": 0,
                "held_back_count": 0,
            }

        row.status = GradePromotionRequestStatus.EXECUTING
        await self._session.flush()

        try:
            target = await self._ensure_grade(
                school_id=school_id,
                name=row.target_grade_name,
                academic_session=row.target_academic_session,
                promoted_from_grade_id=source.id,
            )
            held_back_grade = await self._ensure_grade(
                school_id=school_id,
                name=source.name,
                academic_session=row.target_academic_session,
                promoted_from_grade_id=None,
            )

            enrollments = await self._enrollments.list_active_for_grade(
                source.id, source.academic_session
            )
            exclusion = set(row.exclusion_list_jsonb or [])
            promoted_count = 0
            held_back_count = 0
            for enrollment in enrollments:
                if enrollment.student_user_id in exclusion:
                    await self._repoint_enrollment(enrollment, target_grade=held_back_grade)
                    held_back_count += 1
                else:
                    await self._repoint_enrollment(enrollment, target_grade=target)
                    promoted_count += 1

            now = datetime.now(timezone.utc)
            row.target_grade_id = target.id
            row.status = GradePromotionRequestStatus.EXECUTED
            row.executed_at = now
            await self._session.commit()

            await audit(
                session=self._session,
                action="promotion.executed",
                actor_id=None,
                actor_role="system",
                target_type="grade_promotion_request",
                target_id=row.id,
                school_id=school_id,
                metadata={
                    "promoted_count": promoted_count,
                    "held_back_count": held_back_count,
                    "target_grade_id": target.id,
                },
            )
            logger.info(
                "promotion.executed",
                request_id=row.id,
                promoted_count=promoted_count,
                held_back_count=held_back_count,
            )
            return {
                "request_id": row.id,
                "deferred_final_grade": False,
                "promoted_count": promoted_count,
                "held_back_count": held_back_count,
                "target_grade_id": target.id,
            }
        except Exception as exc:
            await self._session.rollback()
            await self._record_execute_failure(promotion_request_id, school_id, exc)
            raise

    async def _record_execute_failure(
        self,
        promotion_request_id: str,
        school_id: str,
        exc: Exception,
    ) -> None:
        row = await self._requests.get_by_id(promotion_request_id)
        if row is None or row.school_id != school_id:
            return
        row.retry_count = int(row.retry_count or 0) + 1
        row.failure_reason = str(exc)[:2000]
        if row.retry_count > EXECUTE_MAX_RETRIES:
            row.status = GradePromotionRequestStatus.FAILED
            await self._notify_execution_failed(row)
        else:
            # Stay / return to approved so a retry can re-enter executing.
            row.status = GradePromotionRequestStatus.APPROVED
        await self._session.commit()

    async def _notify_execution_failed(self, row: GradePromotionRequest) -> None:
        """Hook for T-255 (account.promotion_execution_failed)."""
        logger.error(
            "promotion.execution_failed_terminal",
            request_id=row.id,
            school_id=row.school_id,
            retry_count=row.retry_count,
            failure_reason=row.failure_reason,
        )
