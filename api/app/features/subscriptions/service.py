"""Subscription Tiers service — business logic for tier management."""

from __future__ import annotations

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.features.subscriptions.models import SubscriptionTier
from app.features.subscriptions.repository import SubscriptionRepository
from app.features.subscriptions.schemas import SubscriptionTierCreate, SubscriptionTierUpdate

logger = structlog.get_logger(__name__)


class SubscriptionService:
    def __init__(self, session: AsyncSession) -> None:
        self._repo = SubscriptionRepository(session)

    async def list_tiers(self) -> list[SubscriptionTier]:
        """List all non-deleted subscription tiers."""
        return await self._repo.list_tiers()

    async def get_tier(self, id: str) -> SubscriptionTier:
        """Fetch a tier by ID; raises NotFoundError if missing or soft-deleted."""
        tier = await self._repo.get_tier_by_id(id)
        if tier is None or tier.deleted_at is not None:
            raise NotFoundError(f"Subscription tier '{id}' not found")
        return tier

    async def create_tier(
        self,
        payload: SubscriptionTierCreate,
        created_by: str,
    ) -> SubscriptionTier:
        """Create a new subscription tier; raises ConflictError on slug collision."""
        existing = await self._repo.get_tier_by_slug(payload.slug)
        if existing is not None:
            raise ConflictError(f"A subscription tier with slug '{payload.slug}' already exists")

        tier = SubscriptionTier(
            name=payload.name,
            slug=payload.slug,
            description=payload.description,
            applies_to=payload.applies_to,
            pricing_monthly_pkr=payload.pricing_monthly_pkr,
            caps=payload.caps,
            is_active=True,
        )
        created = await self._repo.create_tier(tier)
        logger.info(
            "subscription_tier_created",
            tier_id=created.id,
            slug=created.slug,
            by=created_by,
        )
        return created

    async def update_tier(
        self,
        id: str,
        payload: SubscriptionTierUpdate,
        updated_by: str,
    ) -> SubscriptionTier:
        """Update mutable fields on a subscription tier."""
        tier = await self.get_tier(id)

        if payload.name is not None:
            tier.name = payload.name
        if payload.description is not None:
            tier.description = payload.description
        if payload.pricing_monthly_pkr is not None:
            tier.pricing_monthly_pkr = payload.pricing_monthly_pkr
        if payload.caps is not None:
            tier.caps = payload.caps
        if payload.is_active is not None:
            tier.is_active = payload.is_active

        updated = await self._repo.update_tier(tier)
        logger.info(
            "subscription_tier_updated",
            tier_id=updated.id,
            slug=updated.slug,
            by=updated_by,
        )
        return updated

    async def delete_tier(self, id: str) -> None:
        """Soft-delete a subscription tier.

        Active-subscription guard deferred: before deleting, check whether any
        Subscription rows are active against this tier and raise PreconditionFailedError.
        Skipped at launch — Subscription write path is deferred to Phase 2
        per ARCH §3.17 (no Stripe at launch).
        """
        tier = await self.get_tier(id)
        await self._repo.soft_delete_tier(tier)
        logger.info("subscription_tier_deleted", tier_id=id, slug=tier.slug)
