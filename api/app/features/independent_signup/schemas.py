"""Pydantic schemas for independent signup."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.features.independent_users.models import IndependentUserRole


class IndependentSignupInfo(BaseModel):
    roles: list[str]
    languages: list[str]


class IndependentSignupCreate(BaseModel):
    email: str = Field(min_length=3, max_length=255, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=1, max_length=255)
    role: IndependentUserRole
    language_preference: str = Field(default="en", pattern="^(en|ur|sd|ps)$")


class IndependentSignupResponse(BaseModel):
    user_id: str
    email: str
    role: str
    tenant_type: str
    message: str
