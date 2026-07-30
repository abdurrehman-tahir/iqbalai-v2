"""Independent student profile repository."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import not_deleted
from app.features.independent_student_onboarding.models import IndependentStudentProfile


class IndependentStudentProfileRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_user_id(self, user_id: str) -> IndependentStudentProfile | None:
        result = await self._session.execute(
            select(IndependentStudentProfile).where(
                IndependentStudentProfile.user_id == user_id,
                not_deleted(IndependentStudentProfile),
            )
        )
        return result.scalar_one_or_none()

    async def list_with_exam_dates(self) -> list[IndependentStudentProfile]:
        result = await self._session.execute(
            select(IndependentStudentProfile).where(
                IndependentStudentProfile.exam_date.is_not(None),
                not_deleted(IndependentStudentProfile),
            )
        )
        return list(result.scalars().all())

    async def create(self, profile: IndependentStudentProfile) -> IndependentStudentProfile:
        self._session.add(profile)
        await self._session.commit()
        await self._session.refresh(profile)
        return profile

    async def update(self, profile: IndependentStudentProfile) -> IndependentStudentProfile:
        await self._session.commit()
        await self._session.refresh(profile)
        return profile
