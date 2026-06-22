"""Pydantic schemas for parent signup."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ParentSignupInfo(BaseModel):
    languages: list[str]


class ParentSignupCreate(BaseModel):
    email: str = Field(min_length=3, max_length=255, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=1, max_length=255)
    language_preference: str = Field(default="en", pattern="^(en|ur|sd|ps)$")


class ParentSignupResponse(BaseModel):
    user_id: str
    email: str
    role: str
    tenant_type: str
    parent_state: str
    message: str
