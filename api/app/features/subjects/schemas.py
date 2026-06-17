"""Pydantic schemas for Subject endpoints — T-041.

Subjects are the school-scoped catalogue (flow-2 §3.2); a Coordinator (or higher per
§6.19) manages them. The ``…Read`` fields are a strict subset of the ``Subject`` model
columns so the OpenAPI / typed client stay honest (T-225/T-230 schema↔model alignment).
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.features.subjects.models import SubjectStatus


class SubjectRead(BaseModel):
    """Response schema for a single Subject."""

    id: str
    school_id: str
    name: str
    language: str
    status: SubjectStatus
    created_at: datetime

    model_config = {"from_attributes": True}


class SubjectCreate(BaseModel):
    """Payload for creating a new Subject in the caller's school catalogue."""

    name: str = Field(..., min_length=1, max_length=200)
    language: str = Field(..., min_length=1, max_length=20)


class SubjectUpdate(BaseModel):
    """Payload for editing a Subject (all fields optional — PATCH-style merge)."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    language: str | None = Field(default=None, min_length=1, max_length=20)
