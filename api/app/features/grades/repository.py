"""Grade repository — all DB queries (T-043)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import not_deleted
from app.features.grades.models import Grade, GradeStatus


class GradeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_by_school_session(
        self, school_id: str, academic_session: str, include_archived: bool = False
    ) -> list[Grade]:
        stmt = select(Grade).where(
            Grade.school_id == school_id,
            Grade.academic_session == academic_session,
            not_deleted(Grade),
        )
        if not include_archived:
            stmt = stmt.where(Grade.status == GradeStatus.ACTIVE)
        stmt = stmt.order_by(Grade.level_ordinal.asc())
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_id(self, id: str) -> Grade | None:
        result = await self._session.execute(select(Grade).where(Grade.id == id))
        return result.scalar_one_or_none()

    async def get_by_name_session(
        self, school_id: str, name: str, academic_session: str
    ) -> Grade | None:
        result = await self._session.execute(
            select(Grade).where(
                Grade.school_id == school_id,
                Grade.name == name,
                Grade.academic_session == academic_session,
                not_deleted(Grade),
            )
        )
        return result.scalar_one_or_none()

    async def create(self, grade: Grade) -> Grade:
        self._session.add(grade)
        await self._session.commit()
        await self._session.refresh(grade)
        return grade

    async def update(self, grade: Grade) -> Grade:
        await self._session.commit()
        await self._session.refresh(grade)
        return grade
