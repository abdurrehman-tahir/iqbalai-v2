"""JSONB shape schemas for framework study plans (T-091, ARCH §4.10).

These validate the ``framework_study_plans.content_jsonb`` and
``sources_cited_jsonb`` columns on write (Flow 4 §3.5.2). They are content-shape
schemas, not API request/response models — the CRUD/selection endpoints land in
T-092 / T-096.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.features.exam_frameworks.models import FrameworkStatus

# Valid school grade band (Flow 4 §3.5, T-092 Acceptance #4).
_MIN_GRADE = 1
_MAX_GRADE = 14


def _validate_grade_range(value: list[int]) -> list[int]:
    if not value:
        raise ValueError("target_grade_range must not be empty")
    for grade in value:
        if grade < _MIN_GRADE or grade > _MAX_GRADE:
            raise ValueError(f"grade values must be within {_MIN_GRADE}-{_MAX_GRADE}")
    return value


class ExamFrameworkRead(BaseModel):
    """Response schema for a single exam-framework definition."""

    id: str
    name: str
    exam_target: str
    region: str
    target_grade_range: list[int]
    language: str
    status: FrameworkStatus
    created_by: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ExamFrameworkCreate(BaseModel):
    """Payload to create a DRAFT framework definition (Platform Admin)."""

    name: str = Field(..., min_length=1, max_length=255)
    exam_target: str = Field(..., min_length=1, max_length=255)
    region: str = Field(..., min_length=1, max_length=100)
    target_grade_range: list[int] = Field(..., min_length=1)
    language: str = Field(default="en", min_length=2, max_length=10)

    @field_validator("target_grade_range")
    @classmethod
    def _check_grade_range(cls, value: list[int]) -> list[int]:
        return _validate_grade_range(value)


class ExamFrameworkUpdate(BaseModel):
    """Payload to edit a DRAFT framework (all fields optional — merge)."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    exam_target: str | None = Field(default=None, min_length=1, max_length=255)
    region: str | None = Field(default=None, min_length=1, max_length=100)
    target_grade_range: list[int] | None = Field(default=None, min_length=1)
    language: str | None = Field(default=None, min_length=2, max_length=10)

    @field_validator("target_grade_range")
    @classmethod
    def _check_grade_range(cls, value: list[int] | None) -> list[int] | None:
        if value is None:
            return value
        return _validate_grade_range(value)


class SourceCitation(BaseModel):
    """A single cited source for an AI-generated plan."""

    url: str = Field(..., max_length=2048)
    title: str = Field(..., max_length=512)


class FrameworkTopic(BaseModel):
    """One topic within the study plan (§3.5.2 ``topics[]``)."""

    topic_name: str = Field(..., max_length=255)
    # Past-paper weighting in [0, 1]; heavily tested topics approach 1.0.
    priority_weight: float = Field(..., ge=0.0, le=1.0)
    # Past-paper frequency bucket, e.g. "every_year", "alternate_years".
    exam_frequency: str = Field(..., max_length=64)
    recommended_hours: int = Field(..., ge=0)
    key_concepts: list[str] = Field(default_factory=list)
    common_pitfalls: list[str] = Field(default_factory=list)
    past_paper_patterns: str = Field(default="", max_length=4000)
    practice_problems_generated: list[str] = Field(default_factory=list)
    expert_tips: list[str] = Field(default_factory=list)


class WeeklyPacing(BaseModel):
    """One week of the pacing plan (§3.5.2 ``weekly_pacing[]``)."""

    week_from_exam: int = Field(..., ge=0)
    focus_topics: list[str] = Field(default_factory=list)
    hours_estimated: int = Field(..., ge=0)


class ExamStrategy(BaseModel):
    """Exam-day strategy block (§3.5.2 ``exam_strategy``)."""

    time_allocation: str = Field(default="", max_length=2000)
    scoring_strategy: str = Field(default="", max_length=2000)
    common_mistakes: list[str] = Field(default_factory=list)


class FrameworkStudyPlanContent(BaseModel):
    """Full shape of ``framework_study_plans.content_jsonb`` (§3.5.2)."""

    version: int = Field(..., ge=1)
    framework_name: str = Field(..., max_length=255)
    region: str = Field(..., max_length=100)
    target_grade_range: list[int] = Field(default_factory=list)
    sources_cited: list[SourceCitation] = Field(default_factory=list)
    generated_at: str = Field(..., max_length=64)
    topics: list[FrameworkTopic] = Field(default_factory=list)
    weekly_pacing: list[WeeklyPacing] = Field(default_factory=list)
    exam_strategy: ExamStrategy
