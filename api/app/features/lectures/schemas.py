"""JSONB shapes for lecture tables (ARCH §4.10) — T-113.

Validated on write by services in later tickets. Scores remain a nullable
placeholder until M-10 populates the 7-dimension breakdown.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SourceTier(StrEnum):
    """Provenance tier for a generated paragraph (Flow 5 #26 / #27)."""

    CURRICULUM = "curriculum"
    REFERENCE = "reference"
    AI_KNOWLEDGE = "ai_knowledge"
    WEB = "web"  # SearXNG out-of-curriculum fallback


class ParagraphSourceMetadata(BaseModel):
    """Stored in ``lecture_paragraphs.source_metadata_jsonb``."""

    model_config = ConfigDict(extra="forbid")

    tier: SourceTier
    book_name: str | None = None
    chunk_id: str | None = None
    source_url: str | None = None

    def to_jsonb(self) -> dict[str, Any]:
        return self.model_dump(mode="json", exclude_none=True)

    @classmethod
    def from_jsonb(cls, raw: dict[str, Any]) -> ParagraphSourceMetadata:
        return cls.model_validate(raw)


class LectureScores(BaseModel):
    """Placeholder for M-10 7-dimension scores — nullable on versions until then."""

    model_config = ConfigDict(extra="allow")

    dimensions: dict[str, float] = Field(default_factory=dict)

    def to_jsonb(self) -> dict[str, Any]:
        return self.model_dump(mode="json")

    @classmethod
    def from_jsonb(cls, raw: dict[str, Any]) -> LectureScores:
        return cls.model_validate(raw)


class WizardState(BaseModel):
    """Wizard progress blob in ``lecture_drafts.wizard_state_jsonb`` (T-114 fills)."""

    model_config = ConfigDict(extra="allow")

    step: int = Field(ge=1, le=5, default=1)
    data: dict[str, Any] = Field(default_factory=dict)

    def to_jsonb(self) -> dict[str, Any]:
        return self.model_dump(mode="json")

    @classmethod
    def from_jsonb(cls, raw: dict[str, Any]) -> WizardState:
        return cls.model_validate(raw)
