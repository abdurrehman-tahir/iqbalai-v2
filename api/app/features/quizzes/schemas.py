"""JSONB shapes for quiz tables (T-141) — validated on write."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class QuizQuestionOption(BaseModel):
    """One multiple-choice option stored in ``quiz_questions.options_jsonb``."""

    model_config = ConfigDict(extra="forbid")

    key: str = Field(min_length=1, max_length=16)
    text: str = Field(min_length=1, max_length=2000)


class QuizOptionsList(BaseModel):
    """Wrapper so options_jsonb is always a validated list."""

    model_config = ConfigDict(extra="forbid")

    options: list[QuizQuestionOption] = Field(min_length=2, max_length=8)

    def to_jsonb(self) -> list[dict[str, Any]]:
        return [opt.model_dump(mode="json") for opt in self.options]

    @classmethod
    def from_jsonb(cls, raw: object) -> QuizOptionsList:
        if isinstance(raw, list):
            return cls(options=[QuizQuestionOption.model_validate(item) for item in raw])
        if isinstance(raw, dict) and "options" in raw:
            return cls.model_validate(raw)
        raise ValueError("options_jsonb must be a list of {key, text} objects")


class QuestionSourceMetadata(BaseModel):
    """Per-question source attribution (ARCH §4106 / Flow 5 #26).

    Records which lecture content the question was derived from.
    """

    model_config = ConfigDict(extra="forbid")

    lecture_id: str = Field(min_length=1, max_length=36)
    lecture_version_id: str = Field(min_length=1, max_length=36)
    paragraph_id: str | None = Field(default=None, max_length=36)
    paragraph_ordinal: int | None = Field(default=None, ge=1)
    excerpt: str | None = Field(default=None, max_length=2000)
    tier: Literal["curriculum", "reference", "ai_knowledge", "web", "lecture_body"] | None = None

    def to_jsonb(self) -> dict[str, Any]:
        return self.model_dump(mode="json", exclude_none=True)

    @classmethod
    def from_jsonb(cls, raw: dict[str, Any]) -> QuestionSourceMetadata:
        return cls.model_validate(raw)


class CalibrationSource(StrEnum):
    """How calibration inputs were obtained (extensible for M-18)."""

    DIAGNOSTIC_SEED = "diagnostic_seed"
    GRADE_DEFAULT = "grade_default"
    # BLOCKED-HOOK (Flow 9 / M-18): full Cognitive DNA enrichment replaces/extends seed.
    COGNITIVE_DNA = "cognitive_dna"


class CalibrationProfile(BaseModel):
    """Stored in ``quiz_assignments.calibration_jsonb`` (T-144).

    Records the seed inputs used to shape difficulty — not the full DNA engine.
    """

    model_config = ConfigDict(extra="forbid")

    source: CalibrationSource
    topic_confidence: dict[str, float] = Field(default_factory=dict)
    focus_areas: list[str] = Field(default_factory=list)
    target_difficulty: Literal["foundational", "conceptual", "applied", "grade_default"]
    notes: str | None = Field(default=None, max_length=500)

    def to_jsonb(self) -> dict[str, Any]:
        return self.model_dump(mode="json", exclude_none=True)

    @classmethod
    def from_jsonb(cls, raw: dict[str, Any]) -> CalibrationProfile:
        return cls.model_validate(raw)


class QuizAnswersMap(BaseModel):
    """Stored in ``quiz_attempts.answers_jsonb`` — question_id → selected option key."""

    model_config = ConfigDict(extra="forbid")

    answers: dict[str, str] = Field(default_factory=dict)

    def to_jsonb(self) -> dict[str, str]:
        return dict(self.answers)

    @classmethod
    def from_jsonb(cls, raw: object) -> QuizAnswersMap:
        if isinstance(raw, dict):
            # Accept either {"answers": {...}} or a flat map of question_id → key.
            if "answers" in raw and isinstance(raw["answers"], dict):
                return cls.model_validate(raw)
            return cls(answers={str(k): str(v) for k, v in raw.items()})
        raise ValueError("answers_jsonb must be a mapping")
