"""Grade service — business logic (T-043)."""

from __future__ import annotations

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, PermissionDeniedError, ValidationError
from app.features.academic_sessions.repository import AcademicSessionRepository
from app.features.grades.models import Grade, GradeStatus
from app.features.grades.repository import GradeRepository
from app.features.grades.schemas import GradeCreate, GradeUpdate
from app.features.grades.scope import assert_grade_in_scope, derive_level_ordinal
from app.features.offerings.repository import OfferingRepository
from app.features.sections.repository import SectionRepository
from app.features.users.models import User
from app.features.users.repository import UserRepository
from app.infrastructure.audit.log import audit

logger = structlog.get_logger(__name__)


def _caller_school_id(claims: dict[str, object]) -> str:
    raw = claims.get("school_id")
    if raw is None or raw == "":
        raise PermissionDeniedError("School scope required to manage grades")
    return str(raw)


class GradeService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = GradeRepository(session)
        self._user_repo = UserRepository(session)
        self._session_repo = AcademicSessionRepository(session)
        self._section_repo = SectionRepository(session)
        self._offering_repo = OfferingRepository(session)

    async def _load_actor(self, claims: dict[str, object]) -> User:
        # Auth claims use the Authentik user identifier as `sub` (used by /users/me).
        # The internal `users.id` is a different UUID, so we must fetch by authentik_id.
        authentik_id = str(claims.get("sub", ""))
        actor = await self._user_repo.get_by_authentik_id(authentik_id)
        if actor is None:
            raise PermissionDeniedError("User not found")
        return actor

    async def _active_session_label(self, school_id: str) -> str:
        label = await self._session_repo.get_school_active_label(school_id)
        if not label:
            active = await self._session_repo.get_active(school_id)
            label = active.label if active else None
        if not label:
            raise ValidationError("No active academic session — set one before creating grades")
        return label

    async def list_grades(
        self, claims: dict[str, object], include_archived: bool = False
    ) -> list[Grade]:
        school_id = _caller_school_id(claims)
        session_label = await self._active_session_label(school_id)
        grades = await self._repo.list_by_school_session(
            school_id, session_label, include_archived=include_archived
        )
        actor = await self._load_actor(claims)
        scope = None
        from app.core.dependencies import ROLE_HIERARCHY

        if ROLE_HIERARCHY.get(actor.role.value, 0) < ROLE_HIERARCHY["school_admin"]:
            from app.features.grades.scope import parse_grade_scope

            scope = parse_grade_scope(actor.scoped_ids)
            grades = [g for g in grades if g.name in scope]
        return grades

    async def get_grade(self, id: str, claims: dict[str, object]) -> Grade:
        school_id = _caller_school_id(claims)
        grade = await self._repo.get_by_id(id)
        if grade is None or grade.deleted_at is not None or grade.school_id != school_id:
            raise NotFoundError(f"Grade '{id}' not found")
        actor = await self._load_actor(claims)
        assert_grade_in_scope(actor, grade.name)
        return grade

    async def create_grade(
        self, payload: GradeCreate, claims: dict[str, object], actor_id: str
    ) -> Grade:
        school_id = _caller_school_id(claims)
        actor = await self._load_actor(claims)
        assert_grade_in_scope(actor, payload.name)

        session_label = await self._active_session_label(school_id)
        existing = await self._repo.get_by_name_session(school_id, payload.name, session_label)
        if existing is not None:
            raise ConflictError(
                f"A grade named '{payload.name}' already exists for session '{session_label}'"
            )

        grade = Grade(
            school_id=school_id,
            name=payload.name,
            academic_session=session_label,
            level_ordinal=derive_level_ordinal(payload.name),
            status=GradeStatus.ACTIVE,
        )
        created = await self._repo.create(grade)
        await self._section_repo.create_default_internal(created.id)
        await audit(
            session=self._session,
            action="grade.created",
            actor_id=actor_id,
            target_type="grade",
            target_id=created.id,
            school_id=created.school_id,
            metadata={"name": created.name, "academic_session": created.academic_session},
        )
        logger.info("grade_created", grade_id=created.id, school_id=school_id, by=actor_id)
        return created

    async def update_grade(
        self, id: str, payload: GradeUpdate, claims: dict[str, object], actor_id: str
    ) -> Grade:
        grade = await self.get_grade(id, claims)
        if payload.name is not None and payload.name != grade.name:
            actor = await self._load_actor(claims)
            assert_grade_in_scope(actor, payload.name)
            clash = await self._repo.get_by_name_session(
                grade.school_id, payload.name, grade.academic_session
            )
            if clash is not None:
                raise ConflictError(
                    f"A grade named '{payload.name}' already exists for session "
                    f"'{grade.academic_session}'"
                )
            grade.name = payload.name
            grade.level_ordinal = derive_level_ordinal(payload.name)
        updated = await self._repo.update(grade)
        await audit(
            session=self._session,
            action="grade.updated",
            actor_id=actor_id,
            target_type="grade",
            target_id=updated.id,
            school_id=updated.school_id,
            metadata={"name": updated.name},
        )
        return updated

    async def archive_grade(self, id: str, claims: dict[str, object], actor_id: str) -> Grade:
        grade = await self.get_grade(id, claims)
        grade.status = GradeStatus.ARCHIVED
        await self._section_repo.archive_all_for_grade(grade.id)
        await self._offering_repo.archive_all_for_grade(grade.id)
        updated = await self._repo.update(grade)
        await audit(
            session=self._session,
            action="grade.archived",
            actor_id=actor_id,
            target_type="grade",
            target_id=updated.id,
            school_id=updated.school_id,
            metadata={"name": updated.name},
        )
        return updated
