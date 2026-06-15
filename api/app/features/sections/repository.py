"""Section repository — all DB queries (T-044)."""

from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import not_deleted
from app.features.sections.models import Section, SectionStatus


class SectionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_by_grade(self, grade_id: str, include_archived: bool = False) -> list[Section]:
        stmt = select(Section).where(Section.grade_id == grade_id, not_deleted(Section))
        if not include_archived:
            stmt = stmt.where(Section.status == SectionStatus.ACTIVE)
        stmt = stmt.order_by(Section.created_at.asc())
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_visible_by_grade(self, grade_id: str) -> list[Section]:
        """User-facing sections — excludes default-internal."""
        rows = await self.list_by_grade(grade_id)
        return [s for s in rows if not s.is_default_internal]

    async def get_by_id(self, id: str) -> Section | None:
        result = await self._session.execute(select(Section).where(Section.id == id))
        return result.scalar_one_or_none()

    async def get_by_name(self, grade_id: str, name: str) -> Section | None:
        result = await self._session.execute(
            select(Section).where(
                Section.grade_id == grade_id,
                Section.name == name,
                not_deleted(Section),
            )
        )
        return result.scalar_one_or_none()

    async def count_default_internal(self, grade_id: str) -> int:
        rows = await self.list_by_grade(grade_id, include_archived=True)
        return sum(1 for s in rows if s.is_default_internal)

    async def create(self, section: Section) -> Section:
        self._session.add(section)
        await self._session.commit()
        await self._session.refresh(section)
        return section

    async def update(self, section: Section) -> Section:
        await self._session.commit()
        await self._session.refresh(section)
        return section

    async def archive_all_for_grade(self, grade_id: str) -> None:
        await self._session.execute(
            update(Section)
            .where(Section.grade_id == grade_id, not_deleted(Section))
            .values(status=SectionStatus.ARCHIVED)
        )
        await self._session.commit()

    async def create_default_internal(self, grade_id: str) -> Section:
        from app.features.sections.models import DEFAULT_INTERNAL_NAME

        section = Section(
            grade_id=grade_id,
            name=DEFAULT_INTERNAL_NAME,
            is_default_internal=True,
            status=SectionStatus.ACTIVE,
        )
        return await self.create(section)
