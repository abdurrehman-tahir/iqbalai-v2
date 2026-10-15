"""Promotion API schemas — T-250 (Read/Create only; routes land in T-251+)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.features.promotions.models import GradePromotionRequestStatus


class GradePromotionRequestRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    school_id: str
    initiating_grade_id: str
    target_grade_id: str | None = None
    target_academic_session: str
    target_grade_name: str
    initiated_by_coordinator_id: str
    exclusion_list_jsonb: list[str] = Field(default_factory=list)
    status: GradePromotionRequestStatus
    requested_at: datetime
    approved_at: datetime | None = None
    approved_by_user_id: str | None = None
    executed_at: datetime | None = None
    rejection_reason: str | None = None
    failure_reason: str | None = None
    retry_count: int = 0


class GradePromotionRequestCreate(BaseModel):
    """Body intent for T-251 initiate — grade_id comes from the path."""

    target_academic_session: str = Field(min_length=1, max_length=50)
    target_grade_name: str = Field(min_length=1, max_length=200)
    exclusion_list: list[str] = Field(default_factory=list)


class PromotionRosterStudentRead(BaseModel):
    """Active enrollment row for Coordinator exclusion checkboxes (T-251)."""

    student_user_id: str
    display_name: str
    email: str
    enrollment_id: str
    section_id: str


class GradePromotionRejectBody(BaseModel):
    """Optional reject reason — T-252."""

    reason: str | None = Field(default=None, max_length=2000)
