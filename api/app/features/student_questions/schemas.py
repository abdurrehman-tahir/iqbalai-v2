"""API schemas for student lecture questions (T-156 / T-160)."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class QuestionClassificationLiteral(StrEnum):
    MISCONCEPTION = "misconception"
    KNOWLEDGE_GAP = "knowledge_gap"
    UNCLASSIFIED = "unclassified"


class ConversationRoleLiteral(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"


class StudentQuestionCreateRequest(BaseModel):
    """Submit a highlight-triggered (or free-form) question (T-156)."""

    model_config = ConfigDict(extra="forbid")

    question_text: str = Field(min_length=1, max_length=4000)
    highlight_text: str | None = Field(default=None, max_length=4000)
    paragraph_id: str | None = Field(default=None, min_length=1, max_length=36)
    source_chunk_id: str | None = Field(default=None, max_length=128)
    question_language: Literal["en", "ur", "sd", "ps"] = "en"


class StudentQuestionFollowUpRequest(BaseModel):
    """Append a user follow-up turn to an existing conversation (T-160)."""

    model_config = ConfigDict(extra="forbid")

    content: str = Field(min_length=1, max_length=4000)


class ConversationTurnRead(BaseModel):
    id: str
    root_question_id: str
    turn_index: int
    role: ConversationRoleLiteral
    content: str
    source_tags_jsonb: list[object] | dict[str, object] | None = None
    created_at: datetime


class StudentQuestionRead(BaseModel):
    id: str
    student_user_id: str
    session_id: str
    lecture_id: str
    tenant_type: Literal["school", "independent"]
    highlight_text: str | None = None
    question_text: str
    question_language: str
    paragraph_id: str | None = None
    source_chunk_id: str | None = None
    classification: QuestionClassificationLiteral
    answer_text: str | None = None
    answer_source_tags_jsonb: list[object] | dict[str, object] | None = None
    asked_at: datetime
    answered_at: datetime | None = None
    conversations: list[ConversationTurnRead] = Field(default_factory=list)


class AnswerSourceSpanRead(BaseModel):
    """Provenance span for the answer panel (T-158 / T-159)."""

    model_config = ConfigDict(extra="forbid")

    badge: str
    tier: Literal["curriculum", "reference", "ai_knowledge", "web", "no_source"]
    chunk_id: str | None = None
    book_name: str | None = None
    excerpt: str = ""
    source_url: str | None = None


class StudentQuestionAnswerRead(BaseModel):
    """Non-stream snapshot of a generated answer (T-158)."""

    model_config = ConfigDict(extra="forbid")

    question_id: str
    answer_text: str | None = None
    primary_badge: str | None = None
    answer_source_tags_jsonb: list[object] | dict[str, object] | None = None
    answered_at: datetime | None = None
    source_spans: list[AnswerSourceSpanRead] = Field(default_factory=list)
