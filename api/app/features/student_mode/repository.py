"""Repository for school.user_settings — T-101."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import not_deleted
from app.features.student_mode.models import UserSettings


class UserSettingsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_user_id(self, user_id: str) -> UserSettings | None:
        result = await self._session.execute(
            select(UserSettings).where(
                UserSettings.user_id == user_id,
                not_deleted(UserSettings),
            )
        )
        return result.scalar_one_or_none()

    async def create(self, settings: UserSettings) -> UserSettings:
        self._session.add(settings)
        await self._session.commit()
        await self._session.refresh(settings)
        return settings

    async def update(self, settings: UserSettings) -> UserSettings:
        self._session.add(settings)
        await self._session.commit()
        await self._session.refresh(settings)
        return settings
