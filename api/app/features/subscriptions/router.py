"""Subscription Tiers API endpoints — T-022 (Platform Admin only)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db, require_role
from app.core.responses import success
from app.features.subscriptions.schemas import (
    SubscriptionTierCreate,
    SubscriptionTierRead,
    SubscriptionTierUpdate,
)
from app.features.subscriptions.service import SubscriptionService

router = APIRouter(prefix="/admin/subscription-tiers", tags=["subscriptions"])


@router.get(
    "/",
    response_model=dict,
    summary="List all subscription tiers",
    dependencies=[require_role("platform_admin")],
)
async def list_tiers(db: AsyncSession = Depends(get_db)) -> dict:
    svc = SubscriptionService(db)
    tiers = await svc.list_tiers()
    return success([SubscriptionTierRead.model_validate(t).model_dump() for t in tiers])


@router.post(
    "/",
    response_model=dict,
    summary="Create a new subscription tier",
    status_code=201,
    dependencies=[require_role("platform_admin")],
)
async def create_tier(
    payload: SubscriptionTierCreate,
    claims: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    svc = SubscriptionService(db)
    tier = await svc.create_tier(payload, created_by=str(claims.get("sub", "")))
    return success(SubscriptionTierRead.model_validate(tier).model_dump())


@router.get(
    "/{tier_id}",
    response_model=dict,
    summary="Get a single subscription tier",
    dependencies=[require_role("platform_admin")],
)
async def get_tier(
    tier_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    svc = SubscriptionService(db)
    tier = await svc.get_tier(tier_id)
    return success(SubscriptionTierRead.model_validate(tier).model_dump())


@router.put(
    "/{tier_id}",
    response_model=dict,
    summary="Update a subscription tier",
    dependencies=[require_role("platform_admin")],
)
async def update_tier(
    tier_id: str,
    payload: SubscriptionTierUpdate,
    claims: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    svc = SubscriptionService(db)
    tier = await svc.update_tier(tier_id, payload, updated_by=str(claims.get("sub", "")))
    return success(SubscriptionTierRead.model_validate(tier).model_dump())


@router.delete(
    "/{tier_id}",
    response_model=dict,
    summary="Soft-delete a subscription tier",
    dependencies=[require_role("platform_admin")],
)
async def delete_tier(
    tier_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    svc = SubscriptionService(db)
    await svc.delete_tier(tier_id)
    return success({"deleted": True})
