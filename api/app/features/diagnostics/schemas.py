"""Pydantic shapes for diagnostic JSONB + lifecycle I/O — T-103/T-105."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class DiagnosticQuestion(BaseModel):
    """One diagnostic item (filled by T-104 generation / Question Bank hook)."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=64)
    prompt: str = Field(default="", max_length=4000)
    choices: list[str] = Field(default_factory=list)
    topic: str = Field(default="", max_length=255)


class DiagnosticQuestionsBlob(BaseModel):
    model_config = ConfigDict(extra="forbid")

    questions: list[DiagnosticQuestion] = Field(default_factory=list)

    def to_jsonb(self) -> list[object]:
        return [q.model_dump() for q in self.questions]

    @classmethod
    def from_jsonb(cls, raw: list[object] | None) -> DiagnosticQuestionsBlob:
        if not raw:
            return cls()
        questions: list[DiagnosticQuestion] = []
        for item in raw:
            if isinstance(item, dict):
                questions.append(DiagnosticQuestion.model_validate(item))
        return cls(questions=questions)


class DiagnosticAnswersBlob(BaseModel):
    """Map question_id → answer payload (string or structured)."""

    model_config = ConfigDict(extra="forbid")

    answers: dict[str, Any] = Field(default_factory=dict)

    def to_jsonb(self) -> dict[str, object]:
        return dict(self.answers)

    @classmethod
    def from_jsonb(cls, raw: dict[str, Any] | None) -> DiagnosticAnswersBlob:
        if not raw:
            return cls()
        return cls(answers=dict(raw))


DiagnosticStatusLiteral = Literal["not_taken", "in_progress", "completed"]


class DiagnosticRead(BaseModel):
    id: str
    tenant_type: Literal["school", "independent"]
    student_user_id: str
    subject_id: str | None = None
    framework_id: str | None = None
    status: DiagnosticStatusLiteral
    questions: list[DiagnosticQuestion]
    answers: dict[str, Any]
    started_at: datetime | None = None
    completed_at: datetime | None = None
    expires_at: datetime | None = None


class DiagnosticSaveAnswers(BaseModel):
    answers: dict[str, Any] = Field(default_factory=dict)


class DiagnosticStartRequest(BaseModel):
    """Start (or resume active) diagnostic; optionally LLM-generate questions."""

    subject_id: str | None = None
    framework_id: str | None = None
    grade_label: str = ""
    subject_name: str = ""
    framework_name: str = ""
    context_json: dict[str, Any] = Field(default_factory=dict)
    question_count: int = Field(default=20, ge=15, le=25)
    language: Literal["en", "ur", "sd", "ps"] = "en"
    generate: bool = True
    # When generate=False, optional prebuilt questions (demos / tests — not DNA seeding).
    questions: list[DiagnosticQuestion] | None = None


class FocusAreaRead(BaseModel):
    """Coaching focus area — never a grade/score (Flow 4 §3.6 / T-105)."""

    topic: str = Field(min_length=1, max_length=255)
    suggestion: str = Field(min_length=1, max_length=500)


class DiagnosticResultRead(BaseModel):
    """Completion payload for the taking UI. No score/percentage/grade fields."""

    diagnostic: DiagnosticRead
    focus_areas: list[FocusAreaRead]
    timed_out: bool = False
    coaching_summary: str
