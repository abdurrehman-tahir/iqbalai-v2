"""Student question + conversation ORM models — T-156 / T-160 (Flow 6 §3.3–§3.4).

School schema only for now. Independent learners use Flow 8 surfaces later;
do not mirror these tables into ``independent`` until that milestone.

Answer columns (``answer_text``, ``answer_source_tags_jsonb``, ``answered_at``)
are populated by the T-158 RAG answer pipeline.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import AuditMixin, Base, _uuid7


class QuestionClassification(StrEnum):
    """Misconception vs knowledge-gap tagging (T-157 / Flow 6 §3.3)."""

    MISCONCEPTION = "misconception"
    KNOWLEDGE_GAP = "knowledge_gap"
    UNCLASSIFIED = "unclassified"


class ConversationRole(StrEnum):
    """Turn author in a multi-turn Q&A thread (T-160)."""

    USER = "user"
    ASSISTANT = "assistant"


class StudentQuestionTenantType(StrEnum):
    SCHOOL = "school"
    INDEPENDENT = "independent"


def _classification_enum(schema: str) -> SAEnum:
    return SAEnum(
        QuestionClassification,
        name="student_questions_classification_enum",
        schema=schema,
        values_callable=lambda items: [item.value for item in items],
        native_enum=True,
        create_type=False,
    )


def _conversation_role_enum(schema: str) -> SAEnum:
    return SAEnum(
        ConversationRole,
        name="student_question_conversations_role_enum",
        schema=schema,
        values_callable=lambda items: [item.value for item in items],
        native_enum=True,
        create_type=False,
    )


def _tenant_type_enum(schema: str) -> SAEnum:
    # Reuse lectures_tenant_type_enum created by school_0051.
    return SAEnum(
        StudentQuestionTenantType,
        name="lectures_tenant_type_enum",
        schema=schema,
        values_callable=lambda items: [item.value for item in items],
        native_enum=True,
        create_type=False,
    )


class SchoolStudentQuestion(AuditMixin, Base):
    """One student question rooted under a lecture study session (T-156).

    Highlights are transient in M-12 — only ``highlight_text`` is stored
    (persistent ``student_highlights`` / ``highlight_id`` arrive in M-15).
    """

    __tablename__ = "student_questions"
    __table_args__ = (
        Index("ix_student_questions_lecture_id", "lecture_id"),
        Index("ix_student_questions_session_id", "session_id"),
        Index("ix_student_questions_student_user_id", "student_user_id"),
        Index("ix_student_questions_paragraph_id", "paragraph_id"),
        {"schema": "school"},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid7)
    student_user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("school.users.id", ondelete="CASCADE"),
        nullable=False,
    )
    session_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("school.lecture_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    lecture_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("school.lectures.id", ondelete="CASCADE"),
        nullable=False,
    )
    tenant_type: Mapped[StudentQuestionTenantType] = mapped_column(
        _tenant_type_enum("school"),
        nullable=False,
        default=StudentQuestionTenantType.SCHOOL,
    )
    highlight_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    question_language: Mapped[str] = mapped_column(String(8), nullable=False, default="en")
    paragraph_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("school.lecture_paragraphs.id", ondelete="SET NULL"),
        nullable=True,
    )
    # Denormalized from paragraph source_metadata_jsonb.chunk_id (not a hard FK —
    # chunks may live in curriculum or reference corpora).
    source_chunk_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    classification: Mapped[QuestionClassification] = mapped_column(
        _classification_enum("school"),
        nullable=False,
        default=QuestionClassification.UNCLASSIFIED,
    )
    # T-158 answer pipeline fields (nullable until answered).
    answer_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_source_tags_jsonb: Mapped[list[object] | dict[str, object] | None] = mapped_column(
        JSONB, nullable=True
    )
    asked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __init__(self, **kwargs: object) -> None:
        if "id" not in kwargs:
            kwargs["id"] = _uuid7()
        if "tenant_type" not in kwargs:
            kwargs["tenant_type"] = StudentQuestionTenantType.SCHOOL
        if "classification" not in kwargs:
            kwargs["classification"] = QuestionClassification.UNCLASSIFIED
        if "question_language" not in kwargs:
            kwargs["question_language"] = "en"
        super().__init__(**kwargs)


class SchoolStudentQuestionConversation(AuditMixin, Base):
    """One turn in a multi-turn thread under a root student question (T-160)."""

    __tablename__ = "student_question_conversations"
    __table_args__ = (
        UniqueConstraint(
            "root_question_id",
            "turn_index",
            name="student_question_conversations_root_turn_uq",
        ),
        Index("ix_student_question_conversations_root_question_id", "root_question_id"),
        {"schema": "school"},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid7)
    root_question_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("school.student_questions.id", ondelete="CASCADE"),
        nullable=False,
    )
    turn_index: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[ConversationRole] = mapped_column(
        _conversation_role_enum("school"),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source_tags_jsonb: Mapped[list[object] | dict[str, object] | None] = mapped_column(
        JSONB, nullable=True
    )

    def __init__(self, **kwargs: object) -> None:
        if "id" not in kwargs:
            kwargs["id"] = _uuid7()
        super().__init__(**kwargs)
