"""Offering repository — all DB queries (T-045)."""

from __future__ import annotations

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import not_deleted
from app.features.offerings.models import GradeSubjectOffering, OfferingStatus


class OfferingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_by_grade(self, grade_id: str, include_archived: bool = False) -> list[GradeSubjectOffering]:
        stmt = select(GradeSubjectOffering).where(
            GradeSubjectOffering.grade_id == grade_id,
            not_deleted(GradeSubjectOffering),
        )
        if not include_archived:
            stmt = stmt.where(GradeSubjectOffering.status == OfferingStatus.ACTIVE)
        stmt = stmt.order_by(GradeSubjectOffering.created_at.asc())
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_id(self, id: str) -> GradeSubjectOffering | None:
        result = await self._session.execute(
            select(GradeSubjectOffering).where(GradeSubjectOffering.id == id)
        )
        return result.scalar_one_or_none()

    async def get_by_grade_subject(self, grade_id: str, subject_id: str) -> GradeSubjectOffering | None:
        result = await self._session.execute(
            select(GradeSubjectOffering).where(
                GradeSubjectOffering.grade_id == grade_id,
                GradeSubjectOffering.subject_id == subject_id,
                not_deleted(GradeSubjectOffering),
            )
        )
        return result.scalar_one_or_none()

    async def count_active_by_subject(self, subject_id: str) -> int:
        stmt = (
            select(func.count())
            .select_from(GradeSubjectOffering)
            .where(
                GradeSubjectOffering.subject_id == subject_id,
                GradeSubjectOffering.status == OfferingStatus.ACTIVE,
                not_deleted(GradeSubjectOffering),
            )
        )
        result = await self._session.execute(stmt)
        return int(result.scalar_one())

    async def count_active_assignments_for_teacher(self, teacher_id: str) -> int:
        stmt = (
            select(func.count())
            .select_from(GradeSubjectOffering)
            .where(
                GradeSubjectOffering.assigned_teacher_id == teacher_id,
                GradeSubjectOffering.status == OfferingStatus.ACTIVE,
                not_deleted(GradeSubjectOffering),
            )
        )
        result = await self._session.execute(stmt)
        return int(result.scalar_one())

    async def create(self, offering: GradeSubjectOffering) -> GradeSubjectOffering:
        self._session.add(offering)
        await self._session.commit()
        await self._session.refresh(offering)
        return offering

    async def update(self, offering: GradeSubjectOffering) -> GradeSubjectOffering:
        await self._session.commit()
        await self._session.refresh(offering)
        return offering

    async def archive_all_for_grade(self, grade_id: str) -> None:
        await self._session.execute(
            update(GradeSubjectOffering)
            .where(GradeSubjectOffering.grade_id == grade_id, not_deleted(GradeSubjectOffering))
            .values(status=OfferingStatus.ARCHIVED)
        )
        await self._session.commit()
