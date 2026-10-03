"""API schemas for persisted highlights (T-185)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class HighlightMarkRead(BaseModel):
    """Where to draw the yellow mark in the *current* lecture version."""

    model_config = ConfigDict(extra="forbid")

    paragraph_id: str
    offset: int
    length: int


class StudentHighlightRead(BaseModel):
    """A persisted highlight. ``mark`` is null when the anchor no longer maps
    onto the current lecture version (flow-6 §5.5 — the mark drops silently)."""

    model_config = ConfigDict(extra="forbid")

    id: str
    lecture_id: str
    lecture_version_id: str | None = None
    paragraph_ordinal: int
    text_range_offset: int
    text_range_length: int
    highlighted_text: str
    question_id: str | None = None
    concept_tag: str | None = None
    tenant_type: Literal["school", "independent"]
    created_at: datetime
    mark: HighlightMarkRead | None = None
