"""Offering service — business logic (T-045, T-046)."""

from __future__ import annotations

from datetime import datetime, timezone

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import ROLE_HIERARCHY
from app.core.exceptions import (
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    PreconditionFailedError,
    ValidationError,
)
from app.features.grades.service import GradeService
from app.features.offerings.models import GradeSubjectOffering, OfferingStatus
from app.features.offerings.repository import OfferingRepository
from app.features.offerings.schemas import OfferingCreate
from app.features.subjects.models import SubjectStatus
from app.features.subjects.repository import SubjectRepository
from app.features.users.models import UserAccountStatus, UserRole
from app.features.users.repository import UserRepository
from app.infrastructure.audit.log import audit
from app.infrastructure.events.structure import publish_structure_mutation
from app.infrastructure.notifications.account import notify_account_event

logger = structlog.get_logger(__name__)

DEFAULT_TEACHER_CAPACITY = 5
MIN_TEACHER_CAPACITY = 1
MAX_TEACHER_CAPACITY = 20


def _parse_if_match(if_match: str | None, offering: GradeSubjectOffering) -> None:
    """Validate If-Match against offering.updated_at (ARCH §5.10)."""
    if if_match is None or if_match.strip() == "":
        return
    supplied = if_match.strip().strip('"')
    try:
        parsed = datetime.fromisoformat(supplied.replace("Z", "+00:00"))
    except ValueError:
        raise PreconditionFailedError(
            "Offering was modified by another request — refresh and retry"
        )
    expected = offering.updated_at
    if parsed != expected and parsed.replace(microsecond=0) != expected.replace(microsecond=0):
        raise PreconditionFailedError(
            "Offering was modified by another request — refresh and retry"
        )


def _teacher_capacity(user) -> int:
    raw = getattr(user, "teacher_capacity", None)
    if raw is None:
        return DEFAULT_TEACHER_CAPACITY
    return max(MIN_TEACHER_CAPACITY, min(MAX_TEACHER_CAPACITY, int(raw)))


class OfferingService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = OfferingRepository(session)
        self._grade_svc = GradeService(session)
        self._subject_repo = SubjectRepository(session)
        self._user_repo = UserRepository(session)

    async def list_offerings(self, grade_id: str, claims: dict[str, object]) -> list[GradeSubjectOffering]:
        await self._grade_svc.get_grade(grade_id, claims)
        return await self._repo.list_by_grade(grade_id)

    async def create_offering(
        self, grade_id: str, payload: OfferingCreate, claims: dict[str, object], actor_id: str
    ) -> GradeSubjectOffering:
        grade = await self._grade_svc.get_grade(grade_id, claims)
        subject = await self._subject_repo.get_by_id(payload.subject_id)
        if (
            subject is None
            or subject.deleted_at is not None
            or subject.school_id != grade.school_id
            or subject.status != SubjectStatus.ACTIVE
        ):
            raise NotFoundError(f"Subject '{payload.subject_id}' not found")

        existing = await self._repo.get_by_grade_subject(grade_id, payload.subject_id)
        if existing is not None:
            raise ConflictError("This subject is already offered to this grade")

        offering = GradeSubjectOffering(
            school_id=grade.school_id,
            grade_id=grade_id,
            subject_id=payload.subject_id,
            academic_session=grade.academic_session,
            status=OfferingStatus.ACTIVE,
        )
        created = await self._repo.create(offering)
        await audit(
            session=self._session,
            action="offering.created",
            actor_id=actor_id,
            target_type="offering",
            target_id=created.id,
            school_id=created.school_id,
            metadata={
                "grade_id": grade_id,
                "subject_id": created.subject_id,
                "academic_session": created.academic_session,
            },
        )
        await publish_structure_mutation(
            "offering_created",
            {"offering_id": created.id, "grade_id": grade_id, "subject_id": created.subject_id},
            school_id=created.school_id,
            user_id=actor_id,
        )
        return created

    async def archive_offering(
        self, grade_id: str, offering_id: str, claims: dict[str, object], actor_id: str
    ) -> GradeSubjectOffering:
        await self._grade_svc.get_grade(grade_id, claims)
        offering = await self._repo.get_by_id(offering_id)
        if (
            offering is None
            or offering.deleted_at is not None
            or offering.grade_id != grade_id
        ):
            raise NotFoundError(f"Offering '{offering_id}' not found")
        offering.status = OfferingStatus.ARCHIVED
        updated = await self._repo.update(offering)
        await audit(
            session=self._session,
            action="offering.archived",
            actor_id=actor_id,
            target_type="offering",
            target_id=updated.id,
            school_id=updated.school_id,
            metadata={"grade_id": grade_id, "subject_id": updated.subject_id},
        )
        await publish_structure_mutation(
            "offering_archived",
            {"offering_id": updated.id, "grade_id": grade_id},
            school_id=updated.school_id,
            user_id=actor_id,
        )
        return updated

    async def list_eligible_teachers(
        self, grade_id: str, claims: dict[str, object]
    ) -> list[dict[str, object]]:
        grade = await self._grade_svc.get_grade(grade_id, claims)
        teachers = await self._user_repo.list_by_school_and_role(grade.school_id, UserRole.TEACHER)
        rows: list[dict[str, object]] = []
        for teacher in teachers:
            if teacher.status != UserAccountStatus.ACTIVE:
                continue
            count = await self._repo.count_active_assignments_for_teacher(teacher.id)
            capacity = _teacher_capacity(teacher)
            rows.append(
                {
                    "id": teacher.id,
                    "display_name": teacher.display_name,
                    "email": teacher.email,
                    "assignment_count": count,
                    "capacity": capacity,
                    "at_capacity": count >= capacity,
                }
            )
        return rows

    async def assign_teacher(
        self,
        grade_id: str,
        offering_id: str,
        teacher_id: str,
        claims: dict[str, object],
        actor_id: str,
        *,
        override: bool = False,
        if_match: str | None = None,
    ) -> GradeSubjectOffering:
        grade = await self._grade_svc.get_grade(grade_id, claims)
        offering = await self._repo.get_by_id(offering_id)
        if (
            offering is None
            or offering.deleted_at is not None
            or offering.grade_id != grade_id
            or offering.status != OfferingStatus.ACTIVE
        ):
            raise NotFoundError(f"Offering '{offering_id}' not found")

        _parse_if_match(if_match, offering)

        teacher = await self._user_repo.get_by_id(teacher_id)
        if (
            teacher is None
            or teacher.deleted_at is not None
            or teacher.school_id != grade.school_id
            or teacher.role != UserRole.TEACHER
            or teacher.status != UserAccountStatus.ACTIVE
        ):
            raise NotFoundError(f"Teacher '{teacher_id}' not found")

        actor = await self._user_repo.get_by_id(actor_id)
        if actor is None:
            raise PermissionDeniedError("User not found")

        capacity = _teacher_capacity(teacher)
        current_count = await self._repo.count_active_assignments_for_teacher(teacher_id)
        if offering.assigned_teacher_id != teacher_id and current_count >= capacity:
            caller_level = ROLE_HIERARCHY.get(actor.role.value, 0)
            can_override = caller_level >= ROLE_HIERARCHY["school_admin"] and override
            if not can_override:
                raise PreconditionFailedError(
                    f"Teacher {teacher.display_name} is at capacity ({current_count}/{capacity})"
                )
            await audit(
                session=self._session,
                action="capacity.override",
                actor_id=actor_id,
                actor_role=actor.role.value,
                target_type="user",
                target_id=teacher_id,
                school_id=grade.school_id,
                metadata={
                    "flagged": True,
                    "teacher_name": teacher.display_name,
                    "assignment_count": current_count,
                    "capacity": capacity,
                    "offering_id": offering_id,
                },
            )
            admins = await self._user_repo.list_by_school_and_role(
                grade.school_id, UserRole.SCHOOL_ADMIN
            )
            for admin in admins:
                if admin.status != UserAccountStatus.ACTIVE:
                    continue
                await notify_account_event(
                    session=self._session,
                    template_key="account.capacity_override",
                    recipient_user_id=admin.id,
                    school_id=grade.school_id,
                    params={
                        "teacher_name": teacher.display_name,
                        "assignment_count": str(current_count),
                        "capacity": str(capacity),
                        "actor_name": actor.display_name,
                    },
                    metadata={"offering_id": offering_id, "teacher_id": teacher_id},
                )

        offering.assigned_teacher_id = teacher_id
        offering.updated_at = datetime.now(timezone.utc)
        updated = await self._repo.update(offering)

        subject = await self._subject_repo.get_by_id(updated.subject_id)
        subject_name = subject.name if subject else updated.subject_id

        await audit(
            session=self._session,
            action="offering.teacher_assigned",
            actor_id=actor_id,
            target_type="offering",
            target_id=updated.id,
            school_id=updated.school_id,
            metadata={
                "teacher_id": teacher_id,
                "grade_id": grade_id,
                "subject_name": subject_name,
            },
        )
        await notify_account_event(
            session=self._session,
            template_key="account.teacher_assigned_offering",
            recipient_user_id=teacher_id,
            school_id=grade.school_id,
            params={
                "grade_name": grade.name,
                "subject_name": subject_name,
            },
            metadata={"offering_id": updated.id},
        )
        await publish_structure_mutation(
            "offering_teacher_assigned",
            {
                "offering_id": updated.id,
                "grade_id": grade_id,
                "teacher_id": teacher_id,
                "override": override,
            },
            school_id=updated.school_id,
            user_id=actor_id,
        )
        return updated

    async def unassign_teacher(
        self,
        grade_id: str,
        offering_id: str,
        claims: dict[str, object],
        actor_id: str,
        *,
        if_match: str | None = None,
    ) -> GradeSubjectOffering:
        await self._grade_svc.get_grade(grade_id, claims)
        offering = await self._repo.get_by_id(offering_id)
        if (
            offering is None
            or offering.deleted_at is not None
            or offering.grade_id != grade_id
        ):
            raise NotFoundError(f"Offering '{offering_id}' not found")

        _parse_if_match(if_match, offering)

        previous_teacher = offering.assigned_teacher_id
        offering.assigned_teacher_id = None
        offering.updated_at = datetime.now(timezone.utc)
        updated = await self._repo.update(offering)
        await audit(
            session=self._session,
            action="offering.teacher_unassigned",
            actor_id=actor_id,
            target_type="offering",
            target_id=updated.id,
            school_id=updated.school_id,
            metadata={"grade_id": grade_id, "teacher_id": previous_teacher},
        )
        await publish_structure_mutation(
            "offering_teacher_unassigned",
            {"offering_id": updated.id, "grade_id": grade_id, "teacher_id": previous_teacher},
            school_id=updated.school_id,
            user_id=actor_id,
        )
        return updated
