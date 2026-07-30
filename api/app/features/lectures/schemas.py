"""API + JSONB schemas for lecture wizard (T-113/T-114)."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SourceTier(StrEnum):
    """Provenance tier for a generated paragraph (Flow 5 #26 / #27)."""

    CURRICULUM = "curriculum"
    REFERENCE = "reference"
    AI_KNOWLEDGE = "ai_knowledge"
    WEB = "web"


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
    """Wizard progress blob in ``lecture_drafts.wizard_state_jsonb``."""

    model_config = ConfigDict(extra="allow")

    step: int = Field(ge=1, le=5, default=1)
    data: dict[str, Any] = Field(default_factory=dict)

    def to_jsonb(self) -> dict[str, Any]:
        return self.model_dump(mode="json")

    @classmethod
    def from_jsonb(cls, raw: dict[str, Any]) -> WizardState:
        return cls.model_validate(raw)


# --- T-114 API schemas ---


class TeacherOfferingRead(BaseModel):
    """Grade-Subject offering assigned to the calling teacher."""

    id: str
    grade_id: str
    grade_name: str
    grade_level_ordinal: int
    subject_id: str
    subject_name: str
    academic_session: str


class WizardCurriculumRead(BaseModel):
    """Curriculum candidate for Step 2 (primary flagged)."""

    id: str
    title: str
    subject_id: str | None
    grade_level_ordinal: int | None
    is_primary: bool
    parse_degraded: bool
    topic_tree_jsonb: dict[str, Any] | None = None


class WizardTopicOption(BaseModel):
    """Flattened topic path from curriculum topic_tree_jsonb."""

    path: str
    label: str


class WizardTopicsRead(BaseModel):
    curriculum_id: str
    parse_degraded: bool
    topics: list[WizardTopicOption]


class LectureDraftRead(BaseModel):
    id: str | None = None
    teacher_user_id: str
    step: int
    data: dict[str, Any]
    updated_at: datetime | None = None


class LectureDraftUpsert(BaseModel):
    """PUT body — full wizard state replace (auto-save)."""

    step: int = Field(ge=1, le=5)
    data: dict[str, Any] = Field(default_factory=dict)


class TeachingMode(StrEnum):
    """Wizard Step 4 teaching mode (Flow 5 §3.1)."""

    AUTO = "auto"
    MANUAL = "manual"
    VOICE_ASSISTED = "voice_assisted"


class WizardReferenceRead(BaseModel):
    """Reference book option for Step 3."""

    id: str
    title: str
    subject_id: str | None
    grade_level_ordinal: int | None
    language: str
    is_cross_grade: bool


class WizardEstimateRead(BaseModel):
    """Step 5 estimated generation time."""

    estimated_seconds: int
    reference_count: int
    teaching_mode: TeachingMode


class LectureGenerateRequest(BaseModel):
    """Commit wizard → create lecture in GENERATING (pipeline is T-116)."""

    grade_subject_offering_id: str = Field(min_length=1, max_length=36)
    topic: str = Field(min_length=1, max_length=500)
    curriculum_id: str = Field(min_length=1, max_length=36)
    reference_book_ids: list[str] = Field(default_factory=list, max_length=20)
    teaching_mode: TeachingMode
    include_cross_grade: bool = False


class LectureGenerateRead(BaseModel):
    lecture_id: str
    status: str
    estimated_seconds: int
