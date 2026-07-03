"""Independent user repository — queries against independent.users."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import not_deleted
from app.features.independent_users.models import IndependentUser


class IndependentUserRepository:
    """Data access for independent-schema user records."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, user_id: str) -> IndependentUser | None:
        result = await self._session.execute(
            select(IndependentUser).where(IndependentUser.id == user_id, not_deleted(IndependentUser))
        )
        return result.scalar_one_or_none()

    async def get_by_authentik_id(self, authentik_id: str) -> IndependentUser | None:
        result = await self._session.execute(
            select(IndependentUser).where(
                IndependentUser.authentik_id == authentik_id,
                not_deleted(IndependentUser),
            )
        )
        return result.scalar_one_or_none()

    async def get_by_authentik_id_any(self, authentik_id: str) -> IndependentUser | None:
        result = await self._session.execute(
            select(IndependentUser).where(IndependentUser.authentik_id == authentik_id)
        )
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> IndependentUser | None:
        result = await self._session.execute(
            select(IndependentUser).where(
                IndependentUser.email == email.lower(),
                IndependentUser.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def create(self, user: IndependentUser) -> IndependentUser:
        self._session.add(user)
        await self._session.commit()
        await self._session.refresh(user)
        return user

    async def update(self, user: IndependentUser) -> IndependentUser:
        await self._session.commit()
        await self._session.refresh(user)
        return user
