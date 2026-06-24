"""Teacher onboarding Pydantic schemas — T-053."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator

from app.features.teacher_onboarding.constants import PAKISTAN_PROVINCES, PLATFORM_LANGUAGES


class TeacherOnboardingState(StrEnum):
    """Server-derived lifecycle state for school teachers (flow-3 §3.1)."""

    PROFILE_INCOMPLETE = "profile_incomplete"
    PROFILE_COMPLETE = "profile_complete"
    READY_TO_TEACH = "ready_to_teach"


class TeacherProfileRead(BaseModel):
    """Teacher profile fields exposed to the caller."""

    user_id: str
    name: str
    region_province: str
    region_district: str | None
    bio: str | None
    language_preference: str
    subject_ids: list[str]
    profile_completed_at: datetime | None

    model_config = {"from_attributes": True}


class TeacherOnboardingRead(BaseModel):
    """Onboarding gate state — ``ready_to_teach`` is derived, never stored."""

    state: TeacherOnboardingState
    profile_complete: bool
    ready_to_teach: bool
    assignment_count: int
    can_create_content: bool
    teacher_capacity: int = 5
    capacity_below_assignments: bool = False
    profile: TeacherProfileRead | None = None


class TeacherCapacityUpdate(BaseModel):
    """Teacher self-edit capacity payload (flow-3 §3.5 — range [1, 20])."""

    teacher_capacity: int = Field(ge=1, le=20)


class TeacherCapacityUpdateRead(BaseModel):
    """Result after updating teacher capacity."""

    teacher_capacity: int
    assignment_count: int
    capacity_below_assignments: bool


class TeacherProfileComplete(BaseModel):
    """Mandatory first-login profile payload (flow-3 §6)."""

    name: str = Field(min_length=1, max_length=255)
    region_province: str = Field(min_length=1, max_length=100)
    region_district: str | None = Field(default=None, max_length=200)
    bio: str | None = Field(default=None, max_length=500)
    language_preference: str = Field(min_length=2, max_length=10)
    subject_ids: list[str] = Field(min_length=1)

    @field_validator("region_province")
    @classmethod
    def validate_province(cls, value: str) -> str:
        normalized = value.strip()
        if normalized not in PAKISTAN_PROVINCES:
            allowed = ", ".join(PAKISTAN_PROVINCES)
            raise ValueError(f"region_province must be one of: {allowed}")
        return normalized

    @field_validator("language_preference")
    @classmethod
    def validate_language(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in PLATFORM_LANGUAGES:
            allowed = ", ".join(PLATFORM_LANGUAGES)
            raise ValueError(f"language_preference must be one of: {allowed}")
        return normalized

    @field_validator("subject_ids")
    @classmethod
    def validate_subject_ids(cls, value: list[str]) -> list[str]:
        cleaned = [item.strip() for item in value if item.strip()]
        if not cleaned:
            raise ValueError("At least one subject is required")
        return cleaned
