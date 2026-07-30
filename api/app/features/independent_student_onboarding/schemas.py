"""Independent student onboarding Pydantic schemas — T-071."""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator


class IndependentStudentOnboardingState(StrEnum):
    PROFILE_INCOMPLETE = "profile_incomplete"
    READY_TO_STUDY = "ready_to_study"


class IndependentStudentProfileRead(BaseModel):
    user_id: str
    name: str
    language_preference: str
    grade_level: int
    exam_syllabus_id: str
    exam_date: date | None
    profile_completed_at: datetime | None
    diagnostic_available: bool = True
    diagnostic_deferred: bool = True

    model_config = {"from_attributes": True}


class IndependentStudentOnboardingRead(BaseModel):
    state: IndependentStudentOnboardingState
    profile_complete: bool
    ready_to_study: bool
    self_study_only: bool = True
    exam_date_passed: bool = False
    future_date_warning: str | None = None
    profile: IndependentStudentProfileRead | None = None


class IndependentStudentProfileComplete(BaseModel):
    exam_date: date = Field(description="Target exam date (required on first login)")

    @field_validator("exam_date")
    @classmethod
    def validate_exam_date_future(cls, value: date) -> date:
        if value < date.today():
            raise ValueError("exam_date must be today or in the future")
        return value


class IndependentStudentExamDateUpdate(BaseModel):
    """Update exam date after profile complete (T-107 EXAM_PASSED re-set)."""

    exam_date: date = Field(description="Target exam date")

    @field_validator("exam_date")
    @classmethod
    def validate_exam_date_future(cls, value: date) -> date:
        if value < date.today():
            raise ValueError("exam_date must be today or in the future")
        return value


class ExamFrameworkOption(BaseModel):
    """Public exam framework option — backed by exam syllabi until M-07."""

    id: str
    name: str
    exam_board: str
    language: str

    model_config = {"from_attributes": True}
