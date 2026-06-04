"""Subscription Tiers repository — all DB queries for tiers."""

from __future__ import annotations

from datetime import datetime, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.subscriptions.models import SubscriptionTier

logger = structlog.get_logger(__name__)


class SubscriptionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_tiers(self) -> list[SubscriptionTier]:
        """Return all non-soft-deleted tiers."""
        result = await self._session.execute(
            select(SubscriptionTier).where(SubscriptionTier.deleted_at.is_(None))
        )
        return list(result.scalars().all())

    async def get_tier_by_id(self, id: str) -> SubscriptionTier | None:
        result = await self._session.execute(
            select(SubscriptionTier).where(SubscriptionTier.id == id)
        )
        return result.scalar_one_or_none()

    async def get_tier_by_slug(self, slug: str) -> SubscriptionTier | None:
        result = await self._session.execute(
            select(SubscriptionTier).where(SubscriptionTier.slug == slug)
        )
        return result.scalar_one_or_none()

    async def create_tier(self, tier: SubscriptionTier) -> SubscriptionTier:
        self._session.add(tier)
        await self._session.commit()
        await self._session.refresh(tier)
        return tier

    async def update_tier(self, tier: SubscriptionTier) -> SubscriptionTier:
        await self._session.commit()
        await self._session.refresh(tier)
        return tier

    async def soft_delete_tier(self, tier: SubscriptionTier) -> None:
        tier.deleted_at = datetime.now(timezone.utc)
        await self._session.commit()
