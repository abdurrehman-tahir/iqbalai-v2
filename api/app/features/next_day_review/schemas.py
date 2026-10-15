"""Next-day review Pydantic schemas — T-195 (Read shapes; routes land later)."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.features.next_day_review.models import LectureReviewStatus


class LectureReviewRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    lecture_id: str
    gso_id: str
    review_date: date
    ai_summary: str
    reflective_prompt: str
    status: LectureReviewStatus
    pending_action: bool
    dismissed_at: datetime | None = None
    acted_actions: list[str] = Field(default_factory=list)
    mini_lecture_id: str | None = None
    created_at: datetime
    updated_at: datetime


class ReviewReplyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    review_id: str
    cluster_id: str
    student_user_id: str
    body: str
    created_at: datetime


class SkippedClusterRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    review_id: str
    cluster_ref: str
    skipped_at: datetime


class ReviewClassificationFailureRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    school_id: str
    gso_id: str
    cluster_ref: str
    error: str
    failed_at: datetime
