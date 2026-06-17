"""Pydantic schemas for Academic Session endpoints — T-042."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


class AcademicSessionRead(BaseModel):
    """Response schema for a single Academic Session."""

    id: str
    school_id: str
    label: str
    is_active: bool
    start_date: date | None
    end_date: date | None
    created_at: datetime

    model_config = {"from_attributes": True}


class AcademicSessionCreate(BaseModel):
    """Payload for creating a new Academic Session."""

    label: str = Field(..., min_length=1, max_length=50)
    start_date: date | None = None
    end_date: date | None = None
    set_active: bool = Field(
        default=False,
        description="If true, mark this session active (deactivates any prior active session)",
    )


class ActiveSessionRead(BaseModel):
    """The school's currently active academic session label (may be null)."""

    label: str | None
    session: AcademicSessionRead | None
