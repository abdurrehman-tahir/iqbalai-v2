"""API + JSONB schemas for lecture wizard (T-113/T-114)."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

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


class VoiceEditOp(StrEnum):
    """Structured draft-edit kind a voice turn can produce (T-121, #25)."""

    NONE = "none"
    INSERT = "insert"
    REPLACE = "replace"
    APPEND = "append"


class VoiceEditOperation(BaseModel):
    """Stored in ``lecture_voice_turns.edit_operation_jsonb``.

    ``ordinal`` targets the paragraph to insert-before or replace; ignored
    (must be ``None``) for ``append``/``none``.
    """

    model_config = ConfigDict(extra="forbid")

    op: VoiceEditOp
    ordinal: int | None = None
    text: str | None = Field(default=None, max_length=8000)

    def to_jsonb(self) -> dict[str, Any]:
        return self.model_dump(mode="json", exclude_none=True)

    @classmethod
    def from_jsonb(cls, raw: dict[str, Any]) -> VoiceEditOperation:
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


class LectureParagraphRead(BaseModel):
    """One paragraph of the lecture's current version, with source attribution (T-118)."""

    ordinal: int
    text: str
    tier: SourceTier
    book_name: str | None = None
    source_url: str | None = None


class LectureLinkCreate(BaseModel):
    """Self-link a lecture into another Grade-Subject offering the teacher owns (T-122)."""

    target_grade_subject_offering_id: str = Field(min_length=1, max_length=36)


class LectureLinkRead(BaseModel):
    """A lecture's link into an additional Grade-Subject offering (T-122, #21)."""

    id: str
    lecture_id: str
    target_grade_subject_offering_id: str
    target_grade_id: str
    target_grade_name: str
    target_grade_level_ordinal: int
    target_subject_id: str
    target_subject_name: str
    created_at: datetime


class LectureAssignmentScope(StrEnum):
    """What a lecture_assignments row restricts access to (T-123, #21)."""

    STUDENT = "student"
    SECTION = "section"


class LectureAssignmentInput(BaseModel):
    """One restriction row in a PUT to the lecture's access settings."""

    model_config = ConfigDict(extra="forbid")

    scope: LectureAssignmentScope
    student_user_id: str | None = Field(default=None, max_length=36)
    section_id: str | None = Field(default=None, max_length=36)


class LectureAssignmentRead(BaseModel):
    """One restriction row, enriched with a display name for the teacher UI (T-123, #21)."""

    id: str
    scope: LectureAssignmentScope
    student_user_id: str | None = None
    student_name: str | None = None
    section_id: str | None = None
    section_name: str | None = None
    created_at: datetime


class LectureAccessSettingsRead(BaseModel):
    """A lecture's current access-restriction state (T-123, #21)."""

    lecture_id: str
    is_restricted: bool
    assignments: list[LectureAssignmentRead]


class LectureAccessSettingsUpdate(BaseModel):
    """Replace-all update for a lecture's restriction rows. Empty list = unrestricted."""

    assignments: list[LectureAssignmentInput] = Field(default_factory=list, max_length=200)


class RosterSectionRead(BaseModel):
    """A section option for the access-restriction picker (T-123, #21)."""

    id: str
    name: str


class RosterStudentRead(BaseModel):
    """A student option for the access-restriction picker (T-123, #21)."""

    id: str
    display_name: str
    section_id: str


class LectureRosterRead(BaseModel):
    """The lecture's grade roster, for building the access-restriction picker."""

    sections: list[RosterSectionRead]
    students: list[RosterStudentRead]


class TeacherTipsRealWorldExample(BaseModel):
    """One of exactly 2 real-world examples (#41) — T-124."""

    title: str
    text: str

    def to_jsonb(self) -> dict[str, Any]:
        return self.model_dump(mode="json")

    @classmethod
    def from_jsonb(cls, raw: dict[str, Any]) -> TeacherTipsRealWorldExample:
        return cls.model_validate(raw)


class TeacherTips(BaseModel):
    """Stored in ``lecture_versions.teacher_tips_jsonb`` (T-124, #28, #41)."""

    model_config = ConfigDict(extra="forbid")

    delivery_tips: list[str]
    technique_demo: str
    real_world_examples: list[TeacherTipsRealWorldExample]
    language: str

    def to_jsonb(self) -> dict[str, Any]:
        return self.model_dump(mode="json")

    @classmethod
    def from_jsonb(cls, raw: dict[str, Any]) -> TeacherTips:
        return cls.model_validate(raw)


class LectureTeacherTipsRead(BaseModel):
    """Teacher-facing delivery tips / technique demo / real-world examples (T-124).

    ``status`` is ``"pending"`` until the background generation call completes
    (or fails silently — tips are supplementary and never block the lecture);
    ``tips`` is only populated once ``status`` is ``"ready"``.
    """

    lecture_id: str
    status: Literal["pending", "ready"]
    tips: TeacherTips | None = None
