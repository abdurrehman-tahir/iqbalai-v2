"""Independent teacher onboarding Pydantic schemas — T-070."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator

from app.features.teacher_onboarding.constants import PLATFORM_LANGUAGES


class IndependentTeacherOnboardingState(StrEnum):
    PROFILE_INCOMPLETE = "profile_incomplete"
    READY_TO_USE = "ready_to_use"


class IndependentTeacherProfileRead(BaseModel):
    user_id: str
    name: str
    language_preference: str
    profile_completed_at: datetime | None

    model_config = {"from_attributes": True}


class IndependentTeacherOnboardingRead(BaseModel):
    state: IndependentTeacherOnboardingState
    profile_complete: bool
    ready_to_use: bool
    can_create_content: bool
    profile: IndependentTeacherProfileRead | None = None


class IndependentTeacherProfileComplete(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    language_preference: str = Field(min_length=2, max_length=10)

    @field_validator("language_preference")
    @classmethod
    def validate_language(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in PLATFORM_LANGUAGES:
            allowed = ", ".join(PLATFORM_LANGUAGES)
            raise ValueError(f"language_preference must be one of: {allowed}")
        return normalized
