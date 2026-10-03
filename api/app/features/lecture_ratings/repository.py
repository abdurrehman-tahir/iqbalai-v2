"""Persistence for lecture ratings (T-192)."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.lecture_ratings.models import SchoolLectureRating


class LectureRatingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_own(self, *, lecture_id: str, student_user_id: str) -> SchoolLectureRating | None:
        result = await self._session.execute(
            select(SchoolLectureRating).where(
                SchoolLectureRating.lecture_id == lecture_id,
                SchoolLectureRating.student_user_id == student_user_id,
            )
        )
        return result.scalars().first()

    async def aggregate(self, lecture_id: str) -> tuple[int, float | None]:
        """(count, average) — the only shape ratings ever leave the DB in for staff."""
        row = (
            await self._session.execute(
                select(
                    func.count(SchoolLectureRating.id), func.avg(SchoolLectureRating.rating)
                ).where(SchoolLectureRating.lecture_id == lecture_id)
            )
        ).one()
        count = int(row[0])
        return count, (float(row[1]) if row[1] is not None else None)
