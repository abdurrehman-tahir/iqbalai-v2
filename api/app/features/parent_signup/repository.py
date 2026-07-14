"""Parent profile repository — T-080."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import not_deleted
from app.features.parent_signup.models import ParentProfile
from app.features.users.models import User, UserAccountStatus, UserRole


class ParentProfileRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_user_id(self, user_id: str) -> ParentProfile | None:
        result = await self._session.execute(
            select(ParentProfile).where(
                ParentProfile.user_id == user_id,
                not_deleted(ParentProfile),
            )
        )
        return result.scalar_one_or_none()

    async def create(self, profile: ParentProfile) -> ParentProfile:
        self._session.add(profile)
        await self._session.commit()
        await self._session.refresh(profile)
        return profile

    async def update(self, profile: ParentProfile) -> ParentProfile:
        await self._session.commit()
        await self._session.refresh(profile)
        return profile

    async def list_stale_unlinked(self, cutoff: datetime) -> list[tuple[User, ParentProfile]]:
        """Return active unlinked parents whose unlinked_since is before cutoff."""
        result = await self._session.execute(
            select(User, ParentProfile)
            .join(ParentProfile, ParentProfile.user_id == User.id)
            .where(
                User.role == UserRole.PARENT,
                User.status == UserAccountStatus.ACTIVE,
                User.deleted_at.is_(None),
                ParentProfile.deleted_at.is_(None),
                ParentProfile.is_email_verified.is_(True),
                ParentProfile.unlinked_since.is_not(None),
                ParentProfile.unlinked_since <= cutoff,
            )
        )
        return [(row[0], row[1]) for row in result.all()]
