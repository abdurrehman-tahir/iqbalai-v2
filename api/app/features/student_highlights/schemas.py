"""API schemas for persisted highlights (T-185)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


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


# --- T-188 My Highlights / flashcards ----------------------------------------


class PairedFlashcardRead(BaseModel):
    """The flashcard paired with a highlight (shared by repeat highlights)."""

    model_config = ConfigDict(extra="forbid")

    id: str
    front_text: str
    back_text: str
    # §5.5: the AI answer failed → empty back the student can fill in.
    back_is_placeholder: bool
    status: Literal["active", "dismissed"]
    concept_tag: str | None = None
    created_at: datetime


class HighlightLectureRefRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    topic: str


class MyHighlightRead(BaseModel):
    """One row of the "My Highlights" tab (chronological, newest first)."""

    model_config = ConfigDict(extra="forbid")

    id: str
    highlighted_text: str
    concept_tag: str | None = None
    created_at: datetime
    lecture: HighlightLectureRefRead
    paragraph_ordinal: int
    question_id: str | None = None
    flashcard: PairedFlashcardRead | None = None


class FlashcardBackUpdate(BaseModel):
    """Edit a flashcard's back (§5.5 placeholder cards are editable)."""

    model_config = ConfigDict(extra="forbid")

    back_text: str = Field(min_length=1, max_length=8000)


class ConceptCountRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    concept_tag: str
    count: int


class LectureHighlightAggregateRead(BaseModel):
    """Anonymous per-lecture highlight/flashcard counts (Coordinator/Admin, §6.19).

    Counts only students who share study activity (#72 is inviolate even for
    aggregates); no highlight text, no student identities.
    """

    model_config = ConfigDict(extra="forbid")

    lecture_id: str
    highlight_count: int
    student_count: int
    flashcard_count: int
    top_concepts: list[ConceptCountRead]
