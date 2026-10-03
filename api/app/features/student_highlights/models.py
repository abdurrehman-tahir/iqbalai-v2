"""Student highlight ORM model — T-185 (Flow 6 §3.6 / §5.5, #58).

School schema only, mirroring ``student_questions`` (the lecture viewer + Q&A
surface is school-only until Flow 8 ships independent self-study).

Anchoring: a highlight is anchored by ``paragraph_ordinal`` + an offset/length
inside that paragraph's text. Paragraph *rows* are per-version (a re-edit
creates new paragraph ids), so the ordinal — not ``paragraph_id`` — is the
stable anchor; ``paragraph_id`` / ``lecture_version_id`` are kept as
informational provenance only (SET NULL). On read, the anchor is re-verified
against the lecture's current version: if the span text no longer matches the
mark is dropped silently (§5.5) while the row — and its flashcard — survive.
"""

from __future__ import annotations

from enum import StrEnum

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import AuditMixin, Base, SoftDeleteMixin, _uuid7


class HighlightTenantType(StrEnum):
    SCHOOL = "school"
    INDEPENDENT = "independent"


def _tenant_type_enum(schema: str) -> SAEnum:
    # Reuse lectures_tenant_type_enum created by school_0051 (as student_questions does).
    return SAEnum(
        HighlightTenantType,
        name="lectures_tenant_type_enum",
        schema=schema,
        values_callable=lambda items: [item.value for item in items],
        native_enum=True,
        create_type=False,
    )


class FlashcardSourceType(StrEnum):
    """Where a flashcard came from (flow-6 §10). ``manual`` is reserved for Flow 8."""

    HIGHLIGHT = "highlight"
    MANUAL = "manual"


class FlashcardStatus(StrEnum):
    ACTIVE = "active"
    DISMISSED = "dismissed"


def _flashcard_source_type_enum(schema: str) -> SAEnum:
    return SAEnum(
        FlashcardSourceType,
        name="student_flashcards_source_type_enum",
        schema=schema,
        values_callable=lambda items: [item.value for item in items],
        native_enum=True,
        create_type=False,
    )


def _flashcard_status_enum(schema: str) -> SAEnum:
    return SAEnum(
        FlashcardStatus,
        name="student_flashcards_status_enum",
        schema=schema,
        values_callable=lambda items: [item.value for item in items],
        native_enum=True,
        create_type=False,
    )


class SchoolStudentHighlight(AuditMixin, SoftDeleteMixin, Base):
    """One persisted highlight (T-185). Soft-delete per flow-6 §5.5."""

    __tablename__ = "student_highlights"
    __table_args__ = (
        CheckConstraint("text_range_offset >= 0", name="student_highlights_offset_nonneg_check"),
        CheckConstraint("text_range_length > 0", name="student_highlights_length_positive_check"),
        CheckConstraint(
            "paragraph_ordinal >= 0", name="student_highlights_paragraph_ordinal_nonneg_check"
        ),
        Index("ix_student_highlights_student_lecture", "student_user_id", "lecture_id"),
        Index("ix_student_highlights_lecture_id", "lecture_id"),
        Index("ix_student_highlights_lecture_version_id", "lecture_version_id"),
        Index("ix_student_highlights_paragraph_id", "paragraph_id"),
        Index("ix_student_highlights_question_id", "question_id"),
        {"schema": "school"},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid7)
    # CASCADE: ARCH §4.6 locks users → highlights CASCADE.
    student_user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("school.users.id", ondelete="CASCADE"),
        nullable=False,
    )
    lecture_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("school.lectures.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Version the highlight was made against (provenance; versions are immutable).
    lecture_version_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("school.lecture_versions.id", ondelete="SET NULL"),
        nullable=True,
    )
    paragraph_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("school.lecture_paragraphs.id", ondelete="SET NULL"),
        nullable=True,
    )
    paragraph_ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    text_range_offset: Mapped[int] = mapped_column(Integer, nullable=False)
    text_range_length: Mapped[int] = mapped_column(Integer, nullable=False)
    highlighted_text: Mapped[str] = mapped_column(Text, nullable=False)
    # ai_response_ref — the question whose answer pairs with this highlight.
    question_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("school.student_questions.id", ondelete="SET NULL"),
        nullable=True,
    )
    # Curriculum sub-topic id (same resolver as M-14 session_difficulty, T-175).
    concept_tag: Mapped[str | None] = mapped_column(String(128), nullable=True)
    tenant_type: Mapped[HighlightTenantType] = mapped_column(
        _tenant_type_enum("school"),
        nullable=False,
        default=HighlightTenantType.SCHOOL,
    )

    def __init__(self, **kwargs: object) -> None:
        if "id" not in kwargs:
            kwargs["id"] = _uuid7()
        if "tenant_type" not in kwargs:
            kwargs["tenant_type"] = HighlightTenantType.SCHOOL
        super().__init__(**kwargs)


class SchoolStudentFlashcard(AuditMixin, SoftDeleteMixin, Base):
    """Auto-generated flashcard from a highlight + AI answer pair (T-186, §3.6).

    Dedupe: ``dedupe_hash`` = sha256(lecture_id, normalised highlight text),
    unique per student among non-deleted cards (partial unique index) — the
    same student highlighting the same text in the same lecture reuses the
    card; two different students each get their own.

    Survives its source highlight: ``source_highlight_id`` is SET NULL, and a
    highlight whose mark drops after a lecture re-edit (§5.5) leaves the card
    untouched. Spaced-repetition state is NOT here — it belongs to Flow 8/9
    (py-fsrs, M-17/M-18); M-15 only creates cards and publishes the event.
    """

    __tablename__ = "student_flashcards"
    __table_args__ = (
        Index(
            "student_flashcards_student_dedupe_uq",
            "student_user_id",
            "dedupe_hash",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index("ix_student_flashcards_student_created", "student_user_id", "created_at"),
        Index("ix_student_flashcards_lecture_id", "lecture_id"),
        Index("ix_student_flashcards_source_highlight_id", "source_highlight_id"),
        {"schema": "school"},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid7)
    student_user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("school.users.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Nullable per flow-6 §10 (manual cards have no lecture). SET NULL: a card's
    # front/back stay useful to the student even if the lecture is hard-removed.
    lecture_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("school.lectures.id", ondelete="SET NULL"),
        nullable=True,
    )
    source_type: Mapped[FlashcardSourceType] = mapped_column(
        _flashcard_source_type_enum("school"),
        nullable=False,
        default=FlashcardSourceType.HIGHLIGHT,
    )
    source_highlight_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("school.student_highlights.id", ondelete="SET NULL"),
        nullable=True,
    )
    concept_tag: Mapped[str | None] = mapped_column(String(128), nullable=True)
    front_text: Mapped[str] = mapped_column(Text, nullable=False)
    # Empty string = placeholder back (AI answer failed, §5.5); never NULL.
    back_text: Mapped[str] = mapped_column(Text, nullable=False)
    dedupe_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[FlashcardStatus] = mapped_column(
        _flashcard_status_enum("school"),
        nullable=False,
        default=FlashcardStatus.ACTIVE,
    )
    tenant_type: Mapped[HighlightTenantType] = mapped_column(
        _tenant_type_enum("school"),
        nullable=False,
        default=HighlightTenantType.SCHOOL,
    )

    def __init__(self, **kwargs: object) -> None:
        if "id" not in kwargs:
            kwargs["id"] = _uuid7()
        if "tenant_type" not in kwargs:
            kwargs["tenant_type"] = HighlightTenantType.SCHOOL
        if "source_type" not in kwargs:
            kwargs["source_type"] = FlashcardSourceType.HIGHLIGHT
        if "status" not in kwargs:
            kwargs["status"] = FlashcardStatus.ACTIVE
        super().__init__(**kwargs)
