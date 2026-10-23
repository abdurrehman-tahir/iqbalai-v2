"""Next-day review Pydantic schemas — T-195 (Read shapes; routes land later)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.features.next_day_review.models import LectureReviewStatus


class ReviewClusterQuestion(BaseModel):
    """One student's exact question inside a cluster snapshot (Flow 7 §3.6)."""

    question_id: str
    student_user_id: str
    question_text: str = ""
    paragraph_id: str | None = None
    source_chunk_id: str | None = None
    occurred_at: str | None = None


class ReviewClusterSnapshot(BaseModel):
    """Shape of each ``lecture_reviews.clusters_jsonb`` element (ARCH §4.10).

    ``column`` decides which card column renders it: a cluster that qualifies
    on criticality goes to Critical, otherwise to High Frequency.
    """

    cluster_ref: str
    lecture_id: str
    column: Literal["critical", "high_frequency"]
    question_count: int
    unique_student_count: int
    criticality: int | None = None
    freq_score: float = 0.0
    representative_question: str = ""
    mini_lecture_id: str | None = None
    questions: list[ReviewClusterQuestion] = Field(default_factory=list)


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
