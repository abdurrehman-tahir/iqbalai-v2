"""Independent teacher profile repository."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import not_deleted
from app.features.independent_teacher_onboarding.models import IndependentTeacherProfile


class IndependentTeacherProfileRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_user_id(self, user_id: str) -> IndependentTeacherProfile | None:
        result = await self._session.execute(
            select(IndependentTeacherProfile).where(
                IndependentTeacherProfile.user_id == user_id,
                not_deleted(IndependentTeacherProfile),
            )
        )
        return result.scalar_one_or_none()

    async def create(self, profile: IndependentTeacherProfile) -> IndependentTeacherProfile:
        self._session.add(profile)
        await self._session.commit()
        await self._session.refresh(profile)
        return profile

    async def update(self, profile: IndependentTeacherProfile) -> IndependentTeacherProfile:
        await self._session.commit()
        await self._session.refresh(profile)
        return profile
