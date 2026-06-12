"""User repository — all SQLAlchemy queries for users."""

from __future__ import annotations

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import not_deleted
from app.features.users.models import User, UserAccountStatus, UserRole

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

    async def get_by_authentik_id_any(self, authentik_id: str) -> User | None:
        """Return a user row regardless of soft-delete (for login/middleware checks)."""
        result = await self._session.execute(
            select(User).where(User.authentik_id == authentik_id)
        )
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        result = await self._session.execute(
            select(User).where(User.email == email.lower(), User.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()

    async def list_by_email(self, email: str) -> list[User]:
        result = await self._session.execute(
            select(User)
            .where(User.email == email.lower(), User.deleted_at.is_(None))
            .order_by(User.created_at.asc())
        )
        return list(result.scalars().all())

    async def create(self, user: User) -> User:
        self._session.add(user)
        await self._session.commit()
        await self._session.refresh(user)
        return user

    async def update(self, user: User) -> User:
        await self._session.commit()
        await self._session.refresh(user)
        return user

    async def list_scoped(
        self,
        *,
        district_id: str | None = None,
        school_id: str | None = None,
    ) -> list[User]:
        stmt = select(User).where(User.deleted_at.is_(None)).order_by(User.created_at.desc())
        if school_id is not None:
            stmt = stmt.where(User.school_id == school_id)
        elif district_id is not None:
            stmt = stmt.where(User.district_id == district_id)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def count_active_admins(
        self,
        *,
        role: UserRole,
        district_id: str | None = None,
        school_id: str | None = None,
    ) -> int:
        stmt = (
            select(func.count())
            .select_from(User)
            .where(
                User.deleted_at.is_(None),
                User.status == UserAccountStatus.ACTIVE,
                User.role == role,
            )
        )
        if role == UserRole.PLATFORM_ADMIN:
            stmt = stmt.where(User.district_id.is_(None), User.school_id.is_(None))
        elif role == UserRole.DISTRICT_ADMIN:
            stmt = stmt.where(User.district_id == district_id)
        elif role == UserRole.SCHOOL_ADMIN:
            stmt = stmt.where(User.school_id == school_id)
        result = await self._session.execute(stmt)
        return int(result.scalar_one())
