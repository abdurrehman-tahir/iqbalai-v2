"""Pydantic schemas for ToS and Disclaimer endpoints."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class TosVersionRead(BaseModel):
    """ToS version response."""

    id: str
    version_number: int
    content_md: str
    language: str
    effective_at: datetime

    model_config = {"from_attributes": True}


class TosVersionCreate(BaseModel):
    """Publish a new ToS version (Platform Admin only)."""

    content_md: str = Field(..., min_length=10)
    language: str = Field(default="en", max_length=10)


class TosAcceptRequest(BaseModel):
    """User accepts the current ToS."""

    tos_version_id: str


class TosAcceptResponse(BaseModel):
    """Confirmation of ToS acceptance."""

    accepted: bool
    tos_version_id: str
    accepted_at: datetime


class DisclaimerVersionRead(BaseModel):
    """Disclaimer version response."""

    id: str
    version_number: int
    content: str
    language: str
    effective_at: datetime

    model_config = {"from_attributes": True}


class DisclaimerVersionCreate(BaseModel):
    """Publish a new Disclaimer version (Platform Admin only). 500-char limit."""

    content: str = Field(..., min_length=5, max_length=500)
    language: str = Field(default="en", max_length=10)
