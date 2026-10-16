"""Repositories for independent self-study user_settings — T-209."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import not_deleted
from app.features.self_study.models import IndependentUserSettings


class IndependentUserSettingsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_user_id(self, user_id: str) -> IndependentUserSettings | None:
        result = await self._session.execute(
            select(IndependentUserSettings).where(
                IndependentUserSettings.user_id == user_id,
                not_deleted(IndependentUserSettings),
            )
        )
        return result.scalar_one_or_none()

    async def create(self, settings: IndependentUserSettings) -> IndependentUserSettings:
        self._session.add(settings)
        await self._session.commit()
        await self._session.refresh(settings)
        return settings

    async def update(self, settings: IndependentUserSettings) -> IndependentUserSettings:
        self._session.add(settings)
        await self._session.commit()
        await self._session.refresh(settings)
        return settings
