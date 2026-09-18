"""Quiz ORM models — T-141 (Flow 5 §3.3, ARCH §4 / §4106).

Four tables in both ``school`` and ``independent`` schemas:
``quizzes``, ``quiz_questions``, ``quiz_assignments``, ``quiz_attempts``.

Per-student calibrated generation creates **one quiz row per student**
(plus questions + one assignment). Independent schema tables exist so the
schemas stay aligned, but auto-quiz generation never populates them
(independent teachers are excluded — T-148).

M-18 hook: ``calibration_jsonb`` / ``CalibrationProfile`` is the extension
point for full Cognitive DNA inputs; M-11 only writes diagnostic-seed fields.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import AuditMixin, Base, SoftDeleteMixin, _uuid7


class QuizStatus(StrEnum):
    """Quiz generation lifecycle (Flow 5 §3.3). Additive-only per ARCH §4.9."""

    REQUESTED = "requested"
    GENERATING = "generating"
    READY = "ready"
    FAILED = "failed"


class QuizAssignmentStatus(StrEnum):
    """Per-student assignment lifecycle (T-141)."""

    PENDING = "pending"
    PUBLISHED = "published"
    ATTEMPTED = "attempted"
    COMPLETED = "completed"


class QuizQuestionDifficulty(StrEnum):
    """Question difficulty shaped by calibration (T-144)."""

    FOUNDATIONAL = "foundational"
    CONCEPTUAL = "conceptual"
    APPLIED = "applied"
    GRADE_DEFAULT = "grade_default"


class QuizTenantType(StrEnum):
    SCHOOL = "school"
    INDEPENDENT = "independent"


def _quiz_status_enum(schema: str) -> SAEnum:
    return SAEnum(
        QuizStatus,
        name="quizzes_status_enum",
        schema=schema,
        values_callable=lambda items: [item.value for item in items],
        native_enum=True,
        create_type=False,
    )


def _assignment_status_enum(schema: str) -> SAEnum:
    return SAEnum(
        QuizAssignmentStatus,
        name="quiz_assignments_status_enum",
        schema=schema,
        values_callable=lambda items: [item.value for item in items],
        native_enum=True,
        create_type=False,
    )


def _difficulty_enum(schema: str) -> SAEnum:
    return SAEnum(
        QuizQuestionDifficulty,
        name="quiz_questions_difficulty_enum",
        schema=schema,
        values_callable=lambda items: [item.value for item in items],
        native_enum=True,
        create_type=False,
    )


def _tenant_type_enum(schema: str) -> SAEnum:
    return SAEnum(
        QuizTenantType,
        name="quizzes_tenant_type_enum",
        schema=schema,
        values_callable=lambda items: [item.value for item in items],
        native_enum=True,
        create_type=False,
    )


# ---------------------------------------------------------------------------
# School schema
# ---------------------------------------------------------------------------


class SchoolQuiz(AuditMixin, SoftDeleteMixin, Base):
    """Per-student quiz shell for a lecture version (school)."""

    __tablename__ = "quizzes"
    __table_args__ = (
        Index("ix_quizzes_lecture_id", "lecture_id"),
        Index("ix_quizzes_lecture_version_id", "lecture_version_id"),
        Index("ix_quizzes_student_user_id", "student_user_id"),
        UniqueConstraint(
            "lecture_version_id",
            "student_user_id",
            name="quizzes_lecture_version_student_uq",
        ),
        {"schema": "school"},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid7)
    tenant_type: Mapped[QuizTenantType] = mapped_column(
        _tenant_type_enum("school"),
        nullable=False,
        default=QuizTenantType.SCHOOL,
    )
    lecture_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("school.lectures.id", ondelete="CASCADE"),
        nullable=False,
    )
    lecture_version_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("school.lecture_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Denormalized for unique(lecture_version, student) + late-enrollment dedupe.
    student_user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("school.users.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[QuizStatus] = mapped_column(
        _quiz_status_enum("school"),
        nullable=False,
        default=QuizStatus.REQUESTED,
    )

    def __init__(self, **kwargs: object) -> None:
        if "id" not in kwargs:
            kwargs["id"] = _uuid7()
        if "tenant_type" not in kwargs:
            kwargs["tenant_type"] = QuizTenantType.SCHOOL
        if "status" not in kwargs:
            kwargs["status"] = QuizStatus.REQUESTED
        super().__init__(**kwargs)


class SchoolQuizQuestion(AuditMixin, SoftDeleteMixin, Base):
    """One calibrated MCQ belonging to a per-student quiz."""

    __tablename__ = "quiz_questions"
    __table_args__ = (
        UniqueConstraint("quiz_id", "ordinal", name="quiz_questions_quiz_ordinal_uq"),
        CheckConstraint("ordinal >= 1", name="quiz_questions_ordinal_positive_check"),
        Index("ix_quiz_questions_quiz_id", "quiz_id"),
        {"schema": "school"},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid7)
    quiz_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("school.quizzes.id", ondelete="CASCADE"),
        nullable=False,
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    stem: Mapped[str] = mapped_column(Text, nullable=False)
    options_jsonb: Mapped[list[object]] = mapped_column(JSONB, nullable=False)
    correct_answer: Mapped[str] = mapped_column(String(16), nullable=False)
    difficulty: Mapped[QuizQuestionDifficulty] = mapped_column(
        _difficulty_enum("school"),
        nullable=False,
        default=QuizQuestionDifficulty.GRADE_DEFAULT,
    )
    source_metadata_jsonb: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)

    def __init__(self, **kwargs: object) -> None:
        if "id" not in kwargs:
            kwargs["id"] = _uuid7()
        if "difficulty" not in kwargs:
            kwargs["difficulty"] = QuizQuestionDifficulty.GRADE_DEFAULT
        if "options_jsonb" not in kwargs:
            kwargs["options_jsonb"] = []
        if "source_metadata_jsonb" not in kwargs:
            kwargs["source_metadata_jsonb"] = {}
        super().__init__(**kwargs)


class SchoolQuizAssignment(AuditMixin, SoftDeleteMixin, Base):
    """Links a student to their quiz; publish flips pending → published."""

    __tablename__ = "quiz_assignments"
    __table_args__ = (
        UniqueConstraint("quiz_id", "student_user_id", name="quiz_assignments_quiz_student_uq"),
        Index("ix_quiz_assignments_quiz_id", "quiz_id"),
        Index("ix_quiz_assignments_student_user_id", "student_user_id"),
        Index("ix_quiz_assignments_status", "status"),
        {"schema": "school"},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid7)
    quiz_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("school.quizzes.id", ondelete="CASCADE"),
        nullable=False,
    )
    student_user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("school.users.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[QuizAssignmentStatus] = mapped_column(
        _assignment_status_enum("school"),
        nullable=False,
        default=QuizAssignmentStatus.PENDING,
    )
    calibration_jsonb: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    def __init__(self, **kwargs: object) -> None:
        if "id" not in kwargs:
            kwargs["id"] = _uuid7()
        if "status" not in kwargs:
            kwargs["status"] = QuizAssignmentStatus.PENDING
        if "calibration_jsonb" not in kwargs:
            kwargs["calibration_jsonb"] = {}
        super().__init__(**kwargs)


class SchoolQuizAttempt(AuditMixin, Base):
    """Immutable scored attempt (one row per assignment; idempotent submit)."""

    __tablename__ = "quiz_attempts"
    __table_args__ = (
        UniqueConstraint("quiz_assignment_id", name="quiz_attempts_assignment_uq"),
        CheckConstraint("score >= 0", name="quiz_attempts_score_nonneg_check"),
        CheckConstraint("max_score >= 1", name="quiz_attempts_max_score_positive_check"),
        CheckConstraint("score <= max_score", name="quiz_attempts_score_lte_max_check"),
        Index("ix_quiz_attempts_quiz_assignment_id", "quiz_assignment_id"),
        {"schema": "school"},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid7)
    quiz_assignment_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("school.quiz_assignments.id", ondelete="CASCADE"),
        nullable=False,
    )
    answers_jsonb: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    max_score: Mapped[int] = mapped_column(Integer, nullable=False)
    attempted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    def __init__(self, **kwargs: object) -> None:
        if "id" not in kwargs:
            kwargs["id"] = _uuid7()
        if "answers_jsonb" not in kwargs:
            kwargs["answers_jsonb"] = {}
        super().__init__(**kwargs)


# ---------------------------------------------------------------------------
# Independent schema (tables exist; auto-quiz must never populate — T-148)
# ---------------------------------------------------------------------------


class IndependentQuiz(AuditMixin, SoftDeleteMixin, Base):
    """Independent-schema quiz shell — never auto-populated."""

    __tablename__ = "quizzes"
    __table_args__ = (
        Index("ix_quizzes_lecture_id", "lecture_id"),
        Index("ix_quizzes_lecture_version_id", "lecture_version_id"),
        Index("ix_quizzes_student_user_id", "student_user_id"),
        UniqueConstraint(
            "lecture_version_id",
            "student_user_id",
            name="quizzes_lecture_version_student_uq",
        ),
        {"schema": "independent"},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid7)
    tenant_type: Mapped[QuizTenantType] = mapped_column(
        _tenant_type_enum("independent"),
        nullable=False,
        default=QuizTenantType.INDEPENDENT,
    )
    lecture_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("independent.lectures.id", ondelete="CASCADE"),
        nullable=False,
    )
    lecture_version_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("independent.lecture_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    student_user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("independent.users.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[QuizStatus] = mapped_column(
        _quiz_status_enum("independent"),
        nullable=False,
        default=QuizStatus.REQUESTED,
    )

    def __init__(self, **kwargs: object) -> None:
        if "id" not in kwargs:
            kwargs["id"] = _uuid7()
        if "tenant_type" not in kwargs:
            kwargs["tenant_type"] = QuizTenantType.INDEPENDENT
        if "status" not in kwargs:
            kwargs["status"] = QuizStatus.REQUESTED
        super().__init__(**kwargs)


class IndependentQuizQuestion(AuditMixin, SoftDeleteMixin, Base):
    __tablename__ = "quiz_questions"
    __table_args__ = (
        UniqueConstraint("quiz_id", "ordinal", name="quiz_questions_quiz_ordinal_uq"),
        CheckConstraint("ordinal >= 1", name="quiz_questions_ordinal_positive_check"),
        Index("ix_quiz_questions_quiz_id", "quiz_id"),
        {"schema": "independent"},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid7)
    quiz_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("independent.quizzes.id", ondelete="CASCADE"),
        nullable=False,
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    stem: Mapped[str] = mapped_column(Text, nullable=False)
    options_jsonb: Mapped[list[object]] = mapped_column(JSONB, nullable=False)
    correct_answer: Mapped[str] = mapped_column(String(16), nullable=False)
    difficulty: Mapped[QuizQuestionDifficulty] = mapped_column(
        _difficulty_enum("independent"),
        nullable=False,
        default=QuizQuestionDifficulty.GRADE_DEFAULT,
    )
    source_metadata_jsonb: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)

    def __init__(self, **kwargs: object) -> None:
        if "id" not in kwargs:
            kwargs["id"] = _uuid7()
        if "difficulty" not in kwargs:
            kwargs["difficulty"] = QuizQuestionDifficulty.GRADE_DEFAULT
        if "options_jsonb" not in kwargs:
            kwargs["options_jsonb"] = []
        if "source_metadata_jsonb" not in kwargs:
            kwargs["source_metadata_jsonb"] = {}
        super().__init__(**kwargs)


class IndependentQuizAssignment(AuditMixin, SoftDeleteMixin, Base):
    __tablename__ = "quiz_assignments"
    __table_args__ = (
        UniqueConstraint("quiz_id", "student_user_id", name="quiz_assignments_quiz_student_uq"),
        Index("ix_quiz_assignments_quiz_id", "quiz_id"),
        Index("ix_quiz_assignments_student_user_id", "student_user_id"),
        Index("ix_quiz_assignments_status", "status"),
        {"schema": "independent"},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid7)
    quiz_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("independent.quizzes.id", ondelete="CASCADE"),
        nullable=False,
    )
    student_user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("independent.users.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[QuizAssignmentStatus] = mapped_column(
        _assignment_status_enum("independent"),
        nullable=False,
        default=QuizAssignmentStatus.PENDING,
    )
    calibration_jsonb: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    def __init__(self, **kwargs: object) -> None:
        if "id" not in kwargs:
            kwargs["id"] = _uuid7()
        if "status" not in kwargs:
            kwargs["status"] = QuizAssignmentStatus.PENDING
        if "calibration_jsonb" not in kwargs:
            kwargs["calibration_jsonb"] = {}
        super().__init__(**kwargs)


class IndependentQuizAttempt(AuditMixin, Base):
    __tablename__ = "quiz_attempts"
    __table_args__ = (
        UniqueConstraint("quiz_assignment_id", name="quiz_attempts_assignment_uq"),
        CheckConstraint("score >= 0", name="quiz_attempts_score_nonneg_check"),
        CheckConstraint("max_score >= 1", name="quiz_attempts_max_score_positive_check"),
        CheckConstraint("score <= max_score", name="quiz_attempts_score_lte_max_check"),
        Index("ix_quiz_attempts_quiz_assignment_id", "quiz_assignment_id"),
        {"schema": "independent"},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid7)
    quiz_assignment_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("independent.quiz_assignments.id", ondelete="CASCADE"),
        nullable=False,
    )
    answers_jsonb: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    max_score: Mapped[int] = mapped_column(Integer, nullable=False)
    attempted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    def __init__(self, **kwargs: object) -> None:
        if "id" not in kwargs:
            kwargs["id"] = _uuid7()
        if "answers_jsonb" not in kwargs:
            kwargs["answers_jsonb"] = {}
        super().__init__(**kwargs)
