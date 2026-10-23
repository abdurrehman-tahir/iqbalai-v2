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


# --- API views (T-201+) ---------------------------------------------------------


class ReviewQuestionView(BaseModel):
    """A student's exact question as the viewer may see it.

    ``student_user_id`` / ``student_name`` are populated for the owning teacher
    only — Coordinator/Admin get the wording without identities (§6.19).
    """

    question_id: str
    question_text: str
    student_user_id: str | None = None
    student_name: str | None = None
    paragraph_id: str | None = None
    source_chunk_id: str | None = None
    occurred_at: str | None = None


class ReviewClusterView(BaseModel):
    cluster_ref: str
    lecture_id: str
    column: Literal["critical", "high_frequency"]
    question_count: int
    unique_student_count: int
    criticality: int | None = None
    representative_question: str
    mini_lecture_id: str | None = None
    skipped: bool = False
    questions: list[ReviewQuestionView] = Field(default_factory=list)


class ReviewSummaryRead(BaseModel):
    """One row of the teacher's Reviews list / a lecture's Reviews tab."""

    id: str
    lecture_id: str
    lecture_title: str
    offering_label: str
    review_date: date
    generated_at: datetime | None = None
    status: LectureReviewStatus
    pending_action: bool
    dismissed_at: datetime | None = None
    acted_actions: list[str] = Field(default_factory=list)
    critical_count: int
    high_frequency_count: int
    read_only: bool


class ReviewDetailRead(ReviewSummaryRead):
    """The full review card (Flow 7 §3.3 locked layout)."""

    ai_summary: str
    reflective_prompt: str
    reflected: bool
    mini_lecture_id: str | None = None
    mini_preview: str | None = None
    mini_published: bool = False
    critical: list[ReviewClusterView] = Field(default_factory=list)
    high_frequency: list[ReviewClusterView] = Field(default_factory=list)
    replies: list[ReviewReplyRead] = Field(default_factory=list)
    # True only for the owning teacher — drives names, replies, skip, reflection.
    is_owner: bool
    # Owner, or an admin allowed to override (audit-logged).
    can_act: bool


class ReflectionCreate(BaseModel):
    """Teacher's answer to the reflective question (typed, or a voice transcript)."""

    response: str = Field(min_length=1, max_length=4000)
