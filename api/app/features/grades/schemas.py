"""Pydantic schemas for Grade endpoints — T-043."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.features.grades.models import GradeStatus


class GradeRead(BaseModel):
    id: str
    school_id: str
    name: str
    academic_session: str
    level_ordinal: int
    promoted_from_grade_id: str | None
    status: GradeStatus
    created_at: datetime

    model_config = {"from_attributes": True}


class GradeCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)


class GradeUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
