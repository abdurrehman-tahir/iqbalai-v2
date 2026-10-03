"""Persistence for student highlights (T-185)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import not_deleted
from app.features.student_highlights.models import SchoolStudentHighlight


class StudentHighlightRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, row: SchoolStudentHighlight) -> SchoolStudentHighlight:
        self._session.add(row)
        await self._session.flush()
        return row

    async def get_by_question_id(self, question_id: str) -> SchoolStudentHighlight | None:
        result = await self._session.execute(
            select(SchoolStudentHighlight).where(
                SchoolStudentHighlight.question_id == question_id,
                not_deleted(SchoolStudentHighlight),
            )
        )
        return result.scalars().first()

    async def list_for_student_lecture(
        self, *, student_user_id: str, lecture_id: str
    ) -> list[SchoolStudentHighlight]:
        """Owner-scoped: rows of *this* student only, never other students'."""
        result = await self._session.execute(
            select(SchoolStudentHighlight)
            .where(
                SchoolStudentHighlight.student_user_id == student_user_id,
                SchoolStudentHighlight.lecture_id == lecture_id,
                not_deleted(SchoolStudentHighlight),
            )
            .order_by(SchoolStudentHighlight.created_at.asc())
        )
        return list(result.scalars().all())
