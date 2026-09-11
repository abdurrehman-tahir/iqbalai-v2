"""T-129 — teacher_ai_memory / teacher_benchmarks data-model tests (offline).

Acceptance (M-10 T-129):
3. teacher_ai_memory exists with a `category` column (extensible — Flow 7
   adds a category later without a migration).
4. teacher_benchmarks has `opted_out` + cohort keys (subject, grade_range, region).
"""

from __future__ import annotations

from pathlib import Path
from typing import cast

from sqlalchemy import CheckConstraint, Table, UniqueConstraint
from sqlalchemy import Enum as SAEnum

from app.db.base import Base
from app.features.teacher_coaching.models import (
    IndependentTeacherAiMemory,
    SchoolTeacherAiMemory,
    SchoolTeacherBenchmark,
    TeacherResponseType,
)

_SCHOOL_DIR = Path(__file__).resolve().parents[4] / "alembic" / "versions" / "school"


def test_teacher_ai_memory_registered_in_both_schemas() -> None:
    for schema in ("school", "independent"):
        assert f"{schema}.teacher_ai_memory" in Base.metadata.tables


def test_teacher_benchmarks_school_only() -> None:
    """Acceptance: N/A for independent teachers — no peer cohort in a
    one-person tenant, so no independent.teacher_benchmarks table exists.
    """
    assert "school.teacher_benchmarks" in Base.metadata.tables
    assert "independent.teacher_benchmarks" not in Base.metadata.tables


def test_category_is_extensible_plain_string_not_enum() -> None:
    """Acceptance #3 — category must not require a migration to extend."""
    for model_cls in (SchoolTeacherAiMemory, IndependentTeacherAiMemory):
        col = cast(Table, model_cls.__table__).columns["category"]
        assert not isinstance(col.type, SAEnum)
        assert col.type.length == 50


def test_teacher_response_enum_stable_three_values() -> None:
    assert list(TeacherResponseType) == [
        TeacherResponseType.ACTED,
        TeacherResponseType.IGNORED,
        TeacherResponseType.NONE,
    ]
    col = SchoolTeacherAiMemory.__table__.columns["teacher_response"]
    assert isinstance(col.type, SAEnum)
    assert set(col.type.enums) == {"acted", "ignored", "none"}


def test_teacher_ai_memory_defaults_and_unique_per_weakness() -> None:
    row = SchoolTeacherAiMemory(
        teacher_user_id="t-1",
        category="scoring_weakness",
        weakness_type="low_originality",
        last_suggestion="Try grounding examples in local Punjab contexts.",
    )
    assert row.frequency == 1
    assert row.teacher_response == TeacherResponseType.NONE
    assert row.tenant_type == "school"

    table = cast(Table, SchoolTeacherAiMemory.__table__)
    uniques = [c for c in table.constraints if isinstance(c, UniqueConstraint)]
    cols = {frozenset(c.columns.keys()) for c in uniques}
    assert frozenset({"teacher_user_id", "category", "weakness_type"}) in cols


def test_teacher_benchmarks_opted_out_and_cohort_keys() -> None:
    """Acceptance #4."""
    table = cast(Table, SchoolTeacherBenchmark.__table__)
    assert "opted_out" in table.columns
    assert table.columns["opted_out"].nullable is False

    uniques = [c for c in table.constraints if isinstance(c, UniqueConstraint)]
    cols = {frozenset(c.columns.keys()) for c in uniques}
    assert frozenset({"teacher_user_id", "subject_id", "grade_range", "region"}) in cols

    row = SchoolTeacherBenchmark(
        teacher_user_id="t-1", subject_id="sub-1", grade_range="9-10", region="Punjab"
    )
    assert row.opted_out is False
    assert row.percentile is None
    assert row.cohort_size is None


def test_teacher_benchmarks_percentile_range_check() -> None:
    table = cast(Table, SchoolTeacherBenchmark.__table__)
    names = {c.name for c in table.constraints if isinstance(c, CheckConstraint)}
    assert "teacher_benchmarks_percentile_range_check" in names
    assert "teacher_benchmarks_cohort_size_nonneg_check" in names


def test_migrations_exist_and_use_idempotent_enum() -> None:
    memory_text = (_SCHOOL_DIR / "0060_teacher_ai_memory.py").read_text(encoding="utf-8")
    assert "teacher_ai_memory_teacher_response_enum" in memory_text
    assert "DO $$" in memory_text
    assert "category" in memory_text
