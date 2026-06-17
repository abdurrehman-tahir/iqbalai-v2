"""Pydantic schemas for Section endpoints — T-044."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.features.sections.models import SectionStatus


class SectionRead(BaseModel):
    id: str
    grade_id: str
    name: str
    is_default_internal: bool
    status: SectionStatus
    created_at: datetime

    model_config = {"from_attributes": True}


class SectionCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
