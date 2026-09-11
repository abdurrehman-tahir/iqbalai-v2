"""T-129 — Edit + scoring data model tests (offline: metadata + JSONB shapes).

Acceptance (M-10 T-129):
1. lecture_edit_sessions + lecture_plagiarism_flags exist with constraints
   (both schemas for edit_sessions; school-only for plagiarism_flags).
2. lecture_versions gains topic_relevance_pct / originality_score / edit_summary,
   remaining otherwise immutable (no update path exists on the model — versions
   have no setter/service update method, per §4.18).
3. Migrations define both schemas correctly and round-trip (verified live in
   T-129's implementation session via `alembic upgrade heads` / `downgrade` —
   this offline suite checks the migration source + ORM metadata agree).
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import cast

from sqlalchemy import CheckConstraint, Table, UniqueConstraint

from app.db.base import Base
from app.features.lectures.models import (
    IndependentLectureEditSession,
    IndependentLectureVersion,
    PlagiarismFlagStatus,
    SchoolLectureEditSession,
    SchoolLecturePlagiarismFlag,
    SchoolLectureVersion,
)

_SCHOOL_DIR = Path(__file__).resolve().parents[4] / "alembic" / "versions" / "school"
_INDEPENDENT_DIR = Path(__file__).resolve().parents[4] / "alembic" / "versions" / "independent"


def test_edit_sessions_registered_in_both_schemas() -> None:
    for schema in ("school", "independent"):
        assert f"{schema}.lecture_edit_sessions" in Base.metadata.tables


def test_plagiarism_flags_school_only() -> None:
    assert "school.lecture_plagiarism_flags" in Base.metadata.tables
    assert "independent.lecture_plagiarism_flags" not in Base.metadata.tables


def test_edit_session_effort_columns_nonneg_checks() -> None:
    tables = (
        cast(Table, SchoolLectureEditSession.__table__),
        cast(Table, IndependentLectureEditSession.__table__),
    )
    for table in tables:
        names = {c.name for c in table.constraints if isinstance(c, CheckConstraint)}
        assert "lecture_edit_sessions_active_ms_nonneg_check" in names
        assert "lecture_edit_sessions_edits_count_nonneg_check" in names
        assert "lecture_edit_sessions_char_delta_nonneg_check" in names
        assert "lecture_edit_sessions_ended_after_started_check" in names
        for col in ("active_ms", "edits_count", "char_delta", "started_at", "teacher_user_id"):
            assert table.columns[col].nullable is False
        assert table.columns["ended_at"].nullable is True
        # lecture_version_id nullable: session may start before the version exists.
        assert table.columns["lecture_version_id"].nullable is True


def test_edit_session_defaults() -> None:
    row = SchoolLectureEditSession(teacher_user_id="t-1")
    assert row.active_ms == 0
    assert row.edits_count == 0
    assert row.char_delta == 0
    assert row.ended_at is None


def test_lecture_version_gains_scoring_columns_still_immutable() -> None:
    """Acceptance #2 — new columns present; no mutation surface added."""
    for table_cls in (SchoolLectureVersion, IndependentLectureVersion):
        table = cast(Table, table_cls.__table__)
        for col in ("topic_relevance_pct", "originality_score", "edit_summary"):
            assert col in table.columns
            assert table.columns[col].nullable is True
        # scores_jsonb already existed pre-M-10 — untouched.
        assert "scores_jsonb" in table.columns

    # The model exposes no update/setter method — the only way to change a row
    # after INSERT is a raw UPDATE issued by the (T-134/T-135/T-136) scoring
    # pipeline directly against these three columns, never through the ORM
    # object returned from a save.
    assert not hasattr(SchoolLectureVersion, "update")
    assert not hasattr(SchoolLectureVersion, "set_scores")


def test_plagiarism_flag_status_enum_and_similarity_range() -> None:
    assert list(PlagiarismFlagStatus) == [
        PlagiarismFlagStatus.OPEN,
        PlagiarismFlagStatus.REVIEWED,
        PlagiarismFlagStatus.DISMISSED,
    ]
    table = cast(Table, SchoolLecturePlagiarismFlag.__table__)
    names = {c.name for c in table.constraints if isinstance(c, CheckConstraint)}
    assert "lecture_plagiarism_flags_similarity_range_check" in names
    row = SchoolLecturePlagiarismFlag(lecture_version_id="v-1", similarity_score=Decimal("0.900"))
    assert row.status == PlagiarismFlagStatus.OPEN


def test_plagiarism_flag_never_referenced_by_teacher_facing_columns() -> None:
    """Privacy rule (ARCH §7.15): matched teacher/version stay nullable/hidden —
    no NOT NULL surface forces a service to always populate (and thus leak) them.
    """
    table = cast(Table, SchoolLecturePlagiarismFlag.__table__)
    assert table.columns["matched_lecture_version_id"].nullable is True
    assert table.columns["teacher_user_id"].nullable is True


def test_migrations_define_expected_objects() -> None:
    school_files = {
        "0058_lecture_edit_sessions.py",
        "0059_lecture_version_scoring_columns.py",
        "0060_teacher_ai_memory.py",
        "0061_teacher_benchmarks.py",
        "0062_lecture_plagiarism_flags.py",
    }
    for name in school_files:
        assert (_SCHOOL_DIR / name).exists(), name

    indie_files = {
        "0014_lecture_edit_sessions.py",
        "0015_lecture_version_scoring_columns.py",
        "0016_teacher_ai_memory.py",
    }
    for name in indie_files:
        assert (_INDEPENDENT_DIR / name).exists(), name

    plagiarism_text = (_SCHOOL_DIR / "0062_lecture_plagiarism_flags.py").read_text(encoding="utf-8")
    assert "lecture_plagiarism_flags_status_enum" in plagiarism_text
    # Idempotent enum creation, never sa.Enum in create_table (AUDIT_LOG [migration-enum-create]).
    assert "DO $$" in plagiarism_text

    benchmarks_text = (_SCHOOL_DIR / "0061_teacher_benchmarks.py").read_text(encoding="utf-8")
    assert "opted_out" in benchmarks_text
    assert "teacher_benchmarks_teacher_cohort_uq" in benchmarks_text


def test_edit_session_unique_constraint_absence_allows_multiple_sessions() -> None:
    """A teacher may open several sessions toward the same in-progress draft —
    no unique constraint on (teacher_user_id, lecture_version_id).
    """
    table = cast(Table, SchoolLectureEditSession.__table__)
    uniques = [c for c in table.constraints if isinstance(c, UniqueConstraint)]
    assert uniques == []
