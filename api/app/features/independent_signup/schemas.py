"""Pydantic schemas for independent signup."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.features.independent_student_onboarding.schemas import ExamFrameworkOption
from app.features.independent_users.models import IndependentUserRole


class IndependentSignupInfo(BaseModel):
    roles: list[str]
    languages: list[str]
    # Public exam-framework catalog surfaced on the signup form (T-238): the
    # independent-student signup picks a required framework pre-auth, so the
    # catalog rides on this already-public signup-info endpoint instead of a
    # `/me/`-prefixed PUBLIC_PATHS bypass (audit C6 / ARCH §6.6).
    exam_frameworks: list[ExamFrameworkOption]


class IndependentSignupCreate(BaseModel):
    email: str = Field(min_length=3, max_length=255, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=1, max_length=255)
    role: IndependentUserRole
    language_preference: str = Field(default="en", pattern="^(en|ur|sd|ps)$")
    grade_level: int | None = Field(default=None, ge=1, le=16)
    exam_syllabus_id: str | None = Field(default=None, min_length=1, max_length=36)


class IndependentSignupResponse(BaseModel):
    user_id: str
    email: str
    role: str
    tenant_type: str
    message: str
