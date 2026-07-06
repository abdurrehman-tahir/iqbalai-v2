"""Student profile repository — T-078."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import not_deleted
from app.features.student_onboarding.models import StudentProfile


class StudentProfileRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_user_id(self, user_id: str) -> StudentProfile | None:
        result = await self._session.execute(
            select(StudentProfile).where(
                StudentProfile.user_id == user_id,
                not_deleted(StudentProfile),
            )
        )
        return result.scalar_one_or_none()

    async def create(self, profile: StudentProfile) -> StudentProfile:
        self._session.add(profile)
        await self._session.commit()
        await self._session.refresh(profile)
        return profile

    async def update(self, profile: StudentProfile) -> StudentProfile:
        await self._session.commit()
        await self._session.refresh(profile)
        return profile

    async def list_with_exam_dates(self) -> list[StudentProfile]:
        result = await self._session.execute(
            select(StudentProfile).where(
                StudentProfile.exam_date.is_not(None),
                not_deleted(StudentProfile),
            )
        )
        return list(result.scalars().all())
