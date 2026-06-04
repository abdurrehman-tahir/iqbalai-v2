"""Pydantic schemas for Subscription Tier endpoints — T-022."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class SubscriptionTierRead(BaseModel):
    """Response schema for a single SubscriptionTier."""

    id: str
    name: str
    slug: str
    description: str | None
    applies_to: str
    pricing_monthly_pkr: int
    caps: dict | None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class SubscriptionTierCreate(BaseModel):
    """Payload for creating a new SubscriptionTier."""

    name: str
    slug: str = Field(..., max_length=50)
    description: str | None = None
    applies_to: Literal["district", "school"]
    pricing_monthly_pkr: int = Field(default=0, ge=0)
    caps: dict | None = None


class SubscriptionTierUpdate(BaseModel):
    """Payload for updating a SubscriptionTier (all fields optional)."""

    name: str | None = None
    description: str | None = None
    pricing_monthly_pkr: int | None = None
    caps: dict | None = None
    is_active: bool | None = None
