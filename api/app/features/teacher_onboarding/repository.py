"""Teacher profile repository — T-053."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import not_deleted
from app.features.teacher_onboarding.models import TeacherProfile


class TeacherProfileRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_user_id(self, user_id: str) -> TeacherProfile | None:
        result = await self._session.execute(
            select(TeacherProfile).where(
                TeacherProfile.user_id == user_id,
                not_deleted(TeacherProfile),
            )
        )
        return result.scalar_one_or_none()

    async def create(self, profile: TeacherProfile) -> TeacherProfile:
        self._session.add(profile)
        await self._session.commit()
        await self._session.refresh(profile)
        return profile

    async def update(self, profile: TeacherProfile) -> TeacherProfile:
        await self._session.commit()
        await self._session.refresh(profile)
        return profile
