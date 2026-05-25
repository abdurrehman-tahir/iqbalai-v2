"""Pydantic schemas for Teaching Personas endpoints — T-021."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class PersonaRead(BaseModel):
    """Response schema for a single TeachingPersona."""

    id: str
    name: str
    slug: str
    is_custom: bool
    is_active: bool
    system_prompt_en: str
    created_at: datetime

    model_config = {"from_attributes": True}


class PersonaUpdate(BaseModel):
    """Payload for updating a TeachingPersona (all fields optional).

    Only Platform Admin may call this. Changes apply to NEW sessions only;
    in-flight sessions continue using the previously cached system prompt.
    """

    system_prompt_en: str | None = Field(default=None, max_length=8000)
    system_prompt_ur: str | None = Field(default=None, max_length=8000)
    system_prompt_sd: str | None = Field(default=None, max_length=8000)
    system_prompt_ps: str | None = Field(default=None, max_length=8000)
    is_active: bool | None = None
