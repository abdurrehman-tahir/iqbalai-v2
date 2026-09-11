"""Teacher-coaching ORM models — T-129 (Flow 5 §3.10–§3.11, ARCH §4.18 / §4.21).

Two tables:

``teacher_ai_memory`` — per-teacher adaptive coaching memory (Teaching
Innovation Record, T-138). Lives in both ``school`` and ``independent``
schemas (independent teachers get a simplified own-memory variant, per the
ticket). NOT to be confused with the student-facing Cognitive DNA model in
``app.features.cognitive_dna`` — that tracks student learning gaps; this
tracks a *teacher's* recurring lecture-writing weaknesses.

``teacher_benchmarks`` — anonymized weekly percentile standing within a
(subject, grade_range, region) cohort (T-139). School schema only: the spec
locks benchmarking as N/A for independent teachers (no peer cohort within a
one-person tenant).

Population logic (memory writes, weekly benchmark computation) is T-138/T-139;
this ticket (T-129) only establishes the schema.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    Boolean,
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
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import AuditMixin, Base, _uuid7


class TeacherResponseType(StrEnum):
    """How a teacher responded to the last coaching suggestion for a weakness row.

    Additive-only per ARCH §4.9. Flow 7/M-16 later adds a ``reflective_response_pattern``
    *category* (not a new response type) — this enum itself is expected to stay
    exactly these three values.
    """

    ACTED = "acted"
    IGNORED = "ignored"
    NONE = "none"


def _teacher_response_enum(schema: str) -> SAEnum:
    return SAEnum(
        TeacherResponseType,
        name="teacher_ai_memory_teacher_response_enum",
        schema=schema,
        values_callable=lambda items: [item.value for item in items],
        native_enum=True,
        create_type=False,
    )


# ---------------------------------------------------------------------------
# School schema
# ---------------------------------------------------------------------------


class SchoolTeacherAiMemory(AuditMixin, Base):
    """One row per (teacher, category, weakness_type) — updated in place as the
    weakness recurs, so T-138's "has the teacher ignored this N times" adaptive
    logic is a single-row read. ``category`` is intentionally a plain string, not
    a Postgres enum: it must stay extensible across future milestones without a
    migration (per ticket note; ARCH §4.16 — editable/growing value sets use a
    string or reference table, not a native enum).
    """

    __tablename__ = "teacher_ai_memory"
    __table_args__ = (
        UniqueConstraint(
            "teacher_user_id",
            "category",
            "weakness_type",
            name="teacher_ai_memory_teacher_category_weakness_uq",
        ),
        CheckConstraint("frequency >= 1", name="teacher_ai_memory_frequency_positive_check"),
        Index("ix_teacher_ai_memory_teacher_user_id", "teacher_user_id"),
        {"schema": "school"},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid7)
    # Denormalized alongside the schema itself (mirrors lectures.tenant_type) so a
    # Platform-Admin cross-schema read never has to infer tenant from context.
    tenant_type: Mapped[str] = mapped_column(String(20), nullable=False, default="school")
    teacher_user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("school.users.id", ondelete="CASCADE"),
        nullable=False,
    )
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    weakness_type: Mapped[str] = mapped_column(String(100), nullable=False)
    frequency: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    last_suggestion: Mapped[str] = mapped_column(Text, nullable=False)
    teacher_response: Mapped[TeacherResponseType] = mapped_column(
        _teacher_response_enum("school"),
        nullable=False,
        default=TeacherResponseType.NONE,
    )

    def __init__(self, **kwargs: object) -> None:
        if "id" not in kwargs:
            kwargs["id"] = _uuid7()
        if "tenant_type" not in kwargs:
            kwargs["tenant_type"] = "school"
        if "frequency" not in kwargs:
            kwargs["frequency"] = 1
        if "teacher_response" not in kwargs:
            kwargs["teacher_response"] = TeacherResponseType.NONE
        super().__init__(**kwargs)


class SchoolTeacherBenchmark(AuditMixin, Base):
    """Weekly anonymized percentile standing (T-139, Flow 5 §3.11 #37).

    ``percentile``/``cohort_size`` stay NULL until the first
    ``benchmark.update_weekly`` beat run computes them, and are cleared (not just
    hidden) whenever ``opted_out`` flips true — an opted-out teacher contributes
    nothing to peer cohorts and retains no stale percentile to leak later.
    """

    __tablename__ = "teacher_benchmarks"
    __table_args__ = (
        UniqueConstraint(
            "teacher_user_id",
            "subject_id",
            "grade_range",
            "region",
            name="teacher_benchmarks_teacher_cohort_uq",
        ),
        CheckConstraint(
            "percentile IS NULL OR (percentile >= 0 AND percentile <= 100)",
            name="teacher_benchmarks_percentile_range_check",
        ),
        CheckConstraint(
            "cohort_size IS NULL OR cohort_size >= 0",
            name="teacher_benchmarks_cohort_size_nonneg_check",
        ),
        Index("ix_teacher_benchmarks_teacher_user_id", "teacher_user_id"),
        Index(
            "ix_teacher_benchmarks_cohort",
            "subject_id",
            "grade_range",
            "region",
        ),
        {"schema": "school"},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid7)
    teacher_user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("school.users.id", ondelete="CASCADE"),
        nullable=False,
    )
    subject_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("school.subjects.id", ondelete="RESTRICT"),
        nullable=False,
    )
    grade_range: Mapped[str] = mapped_column(String(50), nullable=False)
    region: Mapped[str] = mapped_column(String(100), nullable=False)
    percentile: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cohort_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    opted_out: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    def __init__(self, **kwargs: object) -> None:
        if "id" not in kwargs:
            kwargs["id"] = _uuid7()
        if "opted_out" not in kwargs:
            kwargs["opted_out"] = False
        super().__init__(**kwargs)


# ---------------------------------------------------------------------------
# Independent schema — simplified own-memory variant only; no benchmarks table
# (N/A for independent teachers per Flow 5 §3.11 — no peer cohort).
# ---------------------------------------------------------------------------


class IndependentTeacherAiMemory(AuditMixin, Base):
    """Simplified own-memory variant for independent teachers (T-138)."""

    __tablename__ = "teacher_ai_memory"
    __table_args__ = (
        UniqueConstraint(
            "teacher_user_id",
            "category",
            "weakness_type",
            name="teacher_ai_memory_teacher_category_weakness_uq",
        ),
        CheckConstraint("frequency >= 1", name="teacher_ai_memory_frequency_positive_check"),
        Index("ix_teacher_ai_memory_teacher_user_id", "teacher_user_id"),
        {"schema": "independent"},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid7)
    tenant_type: Mapped[str] = mapped_column(String(20), nullable=False, default="independent")
    teacher_user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("independent.users.id", ondelete="CASCADE"),
        nullable=False,
    )
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    weakness_type: Mapped[str] = mapped_column(String(100), nullable=False)
    frequency: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    last_suggestion: Mapped[str] = mapped_column(Text, nullable=False)
    teacher_response: Mapped[TeacherResponseType] = mapped_column(
        _teacher_response_enum("independent"),
        nullable=False,
        default=TeacherResponseType.NONE,
    )

    def __init__(self, **kwargs: object) -> None:
        if "id" not in kwargs:
            kwargs["id"] = _uuid7()
        if "tenant_type" not in kwargs:
            kwargs["tenant_type"] = "independent"
        if "frequency" not in kwargs:
            kwargs["frequency"] = 1
        if "teacher_response" not in kwargs:
            kwargs["teacher_response"] = TeacherResponseType.NONE
        super().__init__(**kwargs)
