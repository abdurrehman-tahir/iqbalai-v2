"""User repository — all SQLAlchemy queries for users."""

from __future__ import annotations

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import not_deleted
from app.features.users.models import User

logger = structlog.get_logger(__name__)


class UserRepository:
    """Data access layer for User records."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, user_id: str) -> User | None:
        result = await self._session.execute(
            select(User).where(User.id == user_id, not_deleted(User))
        )
        return result.scalar_one_or_none()

    async def get_by_authentik_id(self, authentik_id: str) -> User | None:
        result = await self._session.execute(
            select(User).where(User.authentik_id == authentik_id, not_deleted(User))
        )
        return result.scalar_one_or_none()

    async def create(self, user: User) -> User:
        self._session.add(user)
        await self._session.commit()
        await self._session.refresh(user)
        return user

    async def update(self, user: User) -> User:
        await self._session.commit()
        await self._session.refresh(user)
        return user
