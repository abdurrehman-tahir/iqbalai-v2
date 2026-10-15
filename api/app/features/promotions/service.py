"""Promotion initiate service — T-251 (approve/execute later)."""

from __future__ import annotations

from datetime import datetime, timezone

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import ROLE_HIERARCHY
from app.core.exceptions import (
    NotFoundError,
    PermissionDeniedError,
    PreconditionFailedError,
    ValidationError,
)
from app.features.grades.models import Grade
from app.features.grades.repository import GradeRepository
from app.features.grades.scope import assert_grade_in_scope, parse_grade_scope
from app.features.promotions.models import GradePromotionRequest, GradePromotionRequestStatus
from app.features.promotions.repository import GradePromotionRequestRepository
from app.features.promotions.schemas import (
    GradePromotionRequestCreate,
    GradePromotionRequestRead,
    PromotionRosterStudentRead,
)
from app.features.student_enrollments.repository import StudentEnrollmentRepository
from app.features.users.models import User, UserRole
from app.features.users.repository import UserRepository
from app.infrastructure.audit.log import audit

logger = structlog.get_logger(__name__)


class PromotionService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._requests = GradePromotionRequestRepository(session)
        self._grades = GradeRepository(session)
        self._enrollments = StudentEnrollmentRepository(session)
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
