"""Pydantic schemas for District endpoints — T-029.

Districts are the org-hierarchy root (ARCH §3.1, §3.3); only a Platform Admin
manages them. ``region`` and ``language_preference`` are optional descriptive
metadata captured at creation (flow-2 §3.1). The ``…Read`` fields are a strict
subset of the ``District`` model columns so the OpenAPI / typed client stay honest.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class DistrictRead(BaseModel):
    """Response schema for a single District."""

    id: str
    name: str
    region: str | None
    language_preference: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class DistrictCreate(BaseModel):
    """Payload for creating a new District."""

    name: str = Field(..., min_length=1, max_length=200)
    region: str | None = Field(default=None, max_length=200)
    language_preference: str | None = Field(default=None, max_length=20)


class DistrictUpdate(BaseModel):
    """Payload for updating a District (all fields optional)."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    region: str | None = Field(default=None, max_length=200)
    language_preference: str | None = Field(default=None, max_length=20)
