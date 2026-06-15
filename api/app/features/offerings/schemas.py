"""Pydantic schemas for GradeSubjectOffering endpoints — T-045/T-046."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.features.offerings.models import OfferingStatus


class OfferingRead(BaseModel):
    id: str
    school_id: str
    grade_id: str
    subject_id: str
    assigned_teacher_id: str | None
    academic_session: str
    status: OfferingStatus
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class OfferingCreate(BaseModel):
    subject_id: str = Field(..., min_length=1, max_length=36)


class OfferingAssign(BaseModel):
    teacher_id: str = Field(..., min_length=1, max_length=36)
    override: bool = False


class EligibleTeacherRead(BaseModel):
    id: str
    display_name: str
    email: str
    assignment_count: int
    capacity: int
    at_capacity: bool
