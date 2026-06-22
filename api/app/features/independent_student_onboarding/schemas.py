"""Independent student onboarding Pydantic schemas — T-071."""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator

from app.features.teacher_onboarding.constants import PLATFORM_LANGUAGES


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
    profile: IndependentStudentProfileRead | None = None


class IndependentStudentProfileComplete(BaseModel):
    exam_date: date = Field(description="Target exam date (required on first login)")

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
