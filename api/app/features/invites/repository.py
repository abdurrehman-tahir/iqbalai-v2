"""User invite repository — DB access for invitation records (T-030)."""

from __future__ import annotations

from datetime import datetime, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.invites.models import UserInvite, UserInviteStatus

logger = structlog.get_logger(__name__)


class UserInviteRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, invite_id: str) -> UserInvite | None:
        result = await self._session.execute(select(UserInvite).where(UserInvite.id == invite_id))
        return result.scalar_one_or_none()

    async def get_by_token_hash(self, token_hash: str) -> UserInvite | None:
        result = await self._session.execute(
            select(UserInvite).where(UserInvite.token_hash == token_hash)
        )
        return result.scalar_one_or_none()

    async def get_pending_by_email(self, email: str) -> UserInvite | None:
        result = await self._session.execute(
            select(UserInvite).where(
                UserInvite.email == email.lower(),
                UserInvite.status == UserInviteStatus.PENDING,
            )
        )
        return result.scalar_one_or_none()

    async def create(self, invite: UserInvite) -> UserInvite:
        self._session.add(invite)
        await self._session.commit()
        await self._session.refresh(invite)
        return invite

    async def update(self, invite: UserInvite) -> UserInvite:
        await self._session.commit()
        await self._session.refresh(invite)
        return invite

    async def expire_stale_pending(self, invite: UserInvite) -> tuple[UserInvite, bool]:
        """Mark a pending invite as expired when past its TTL. Returns (invite, was_expired)."""
        if invite.status == UserInviteStatus.PENDING and invite.expires_at < datetime.now(
            timezone.utc
        ):
            invite.status = UserInviteStatus.EXPIRED
            updated = await self.update(invite)
            return updated, True
        return invite, False

    async def expire_all_stale_pending(self) -> list[UserInvite]:
        """Bulk-expire pending invites past TTL."""
        now = datetime.now(timezone.utc)
        result = await self._session.execute(
            select(UserInvite).where(
                UserInvite.status == UserInviteStatus.PENDING,
                UserInvite.expires_at < now,
            )
        )
        invites = list(result.scalars().all())
        for invite in invites:
            invite.status = UserInviteStatus.EXPIRED
        if invites:
            await self._session.commit()
        return invites
