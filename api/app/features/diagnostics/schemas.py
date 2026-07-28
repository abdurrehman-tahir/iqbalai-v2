"""Pydantic shapes for diagnostic JSONB + lifecycle I/O — T-103."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class DiagnosticQuestion(BaseModel):
    """Placeholder question shape — T-104 fills real content."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=64)
    prompt: str = Field(default="", max_length=4000)
    choices: list[str] = Field(default_factory=list)


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
