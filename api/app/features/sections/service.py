"""Section service — business logic (T-044)."""

from __future__ import annotations

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.features.grades.service import GradeService
from app.features.sections.models import Section, SectionStatus
from app.features.sections.repository import SectionRepository
from app.features.sections.schemas import SectionCreate
from app.infrastructure.audit.log import audit

logger = structlog.get_logger(__name__)


class SectionService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = SectionRepository(session)
        self._grade_svc = GradeService(session)

    async def list_sections(self, grade_id: str, claims: dict[str, object]) -> list[Section]:
        await self._grade_svc.get_grade(grade_id, claims)
        return await self._repo.list_visible_by_grade(grade_id)

    async def create_section(
        self, grade_id: str, payload: SectionCreate, claims: dict[str, object], actor_id: str
    ) -> Section:
        await self._grade_svc.get_grade(grade_id, claims)
        existing = await self._repo.get_by_name(grade_id, payload.name)
        if existing is not None:
            raise ConflictError(
                f"A section named '{payload.name}' already exists under this grade"
            )

        section = Section(
            grade_id=grade_id,
            name=payload.name,
            is_default_internal=False,
            status=SectionStatus.ACTIVE,
        )
        created = await self._repo.create(section)
        grade = await self._grade_svc.get_grade(grade_id, claims)
        await audit(
            session=self._session,
            action="section.created",
            actor_id=actor_id,
            target_type="section",
            target_id=created.id,
            school_id=grade.school_id,
            metadata={"name": created.name, "grade_id": grade_id},
        )
        return created

    async def archive_section(
        self, grade_id: str, section_id: str, claims: dict[str, object], actor_id: str
    ) -> Section:
        await self._grade_svc.get_grade(grade_id, claims)
        section = await self._repo.get_by_id(section_id)
        if (
            section is None
            or section.deleted_at is not None
            or section.grade_id != grade_id
            or section.is_default_internal
        ):
            raise NotFoundError(f"Section '{section_id}' not found")
        section.status = SectionStatus.ARCHIVED
        updated = await self._repo.update(section)
        grade = await self._grade_svc.get_grade(grade_id, claims)
        await audit(
            session=self._session,
            action="section.archived",
            actor_id=actor_id,
            target_type="section",
            target_id=updated.id,
            school_id=grade.school_id,
            metadata={"name": updated.name},
        )
        return updated
