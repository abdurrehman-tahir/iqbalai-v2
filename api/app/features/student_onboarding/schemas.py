"""School student onboarding schemas — T-078."""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class SchoolStudentOnboardingState(str, Enum):
    INVITED = "invited"
    PROFILE_BASIC = "profile_basic"
    MODE_SELECTION = "mode_selection"
    READY_TO_STUDY = "ready_to_study"


class StudentProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: str
    display_name: str
    language_preference: str
    tos_accepted_at: datetime | None
    profile_basic_completed_at: datetime | None
    lecture_mode_enabled: bool
    self_study_mode_enabled: bool
    deferrable_banner_dismissed: bool
    exam_date: date | None = None


class SchoolStudentOnboardingRead(BaseModel):
    state: SchoolStudentOnboardingState
    profile_basic_complete: bool
    mode_selected: bool
    ready_to_study: bool
    show_complete_profile_banner: bool
    exam_date_set: bool = False
    enrollment_grade_id: str | None = None
    profile: StudentProfileRead | None = None
    future_date_warning: str | None = None


class StudentExamDateUpdate(BaseModel):
    exam_date: date = Field(description="Target exam date")

    @field_validator("exam_date")
    @classmethod
    def validate_not_past(cls, value: date) -> date:
        if value < date.today():
            raise ValueError("Exam date must be today or in the future")
        return value


class StudentProfileBasicComplete(BaseModel):
    display_name: str = Field(min_length=1, max_length=255)
    language_preference: str = Field(min_length=2, max_length=10)
    tos_version_id: str = Field(min_length=1, max_length=36)


class StudentModeSelect(BaseModel):
    lecture_mode: bool = False
    self_study_mode: bool = False

    @model_validator(mode="after")
    def at_least_one_mode(self) -> StudentModeSelect:
        if not self.lecture_mode and not self.self_study_mode:
            raise ValueError("Select at least one study mode")
        return self


class StudentBannerDismiss(BaseModel):
    dismissed: bool = True
