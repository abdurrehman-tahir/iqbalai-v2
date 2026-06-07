"""Notification repository — DB access layer for the notifications feature (T-023)."""

from __future__ import annotations

from datetime import datetime, timezone

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import not_deleted
from app.features.notifications.models import Notification

logger = structlog.get_logger(__name__)


class NotificationRepository:
    """All DB access for notifications. Called only from the router layer."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_user(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Notification]:
        """Return non-deleted notifications for a user, newest first."""
        stmt = (
            select(Notification)
            .where(
                Notification.recipient_user_id == user_id,
                not_deleted(Notification),
            )
            .order_by(Notification.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def count_unread(self, user_id: str) -> int:
        """Return the count of unread, non-deleted notifications for a user."""
        stmt = select(func.count()).where(
            Notification.recipient_user_id == user_id,
            Notification.is_read.is_(False),
            not_deleted(Notification),
        )
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def get_by_id(self, notif_id: str) -> Notification | None:
        """Return a single notification by PK, or None if not found."""
        stmt = select(Notification).where(Notification.id == notif_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def mark_read(self, notif: Notification) -> Notification:
        """Set is_read=True and record the read timestamp, then commit."""
        notif.is_read = True
        notif.read_at = datetime.now(timezone.utc)
        self._session.add(notif)
        await self._session.commit()
        await self._session.refresh(notif)
        return notif
