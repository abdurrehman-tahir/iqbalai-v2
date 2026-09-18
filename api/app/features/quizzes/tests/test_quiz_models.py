"""T-141 — Quiz data-model tests (offline: metadata + JSONB shapes)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import cast

import pytest
from pydantic import ValidationError
from sqlalchemy import CheckConstraint, Table, UniqueConstraint
from sqlalchemy import Enum as SAEnum

from app.db.base import Base
from app.features.quizzes import models as quiz_models
from app.features.quizzes.models import (
    IndependentQuiz,
    IndependentQuizAssignment,
    IndependentQuizAttempt,
    IndependentQuizQuestion,
    QuizAssignmentStatus,
    QuizQuestionDifficulty,
    QuizStatus,
    QuizTenantType,
    SchoolQuiz,
    SchoolQuizAssignment,
    SchoolQuizAttempt,
    SchoolQuizQuestion,
)
from app.features.quizzes.schemas import (
    CalibrationProfile,
    CalibrationSource,
    QuestionSourceMetadata,
    QuizAnswersMap,
    QuizOptionsList,
    QuizQuestionOption,
)

_SCHOOL_MIGRATION = (
    Path(__file__).resolve().parents[4] / "alembic" / "versions" / "school" / "0065_quizzes.py"
)
_INDEPENDENT_MIGRATION = (
    Path(__file__).resolve().parents[4]
    / "alembic"
    / "versions"
    / "independent"
    / "0018_quizzes.py"
)

_FOUR_TABLES = ("quizzes", "quiz_questions", "quiz_assignments", "quiz_attempts")


def test_all_four_tables_registered_in_both_schemas() -> None:
    # Import registers tables on Base.metadata
    assert quiz_models is not None
    for schema in ("school", "independent"):
        for name in _FOUR_TABLES:
            key = f"{schema}.{name}"
            assert key in Base.metadata.tables, f"missing table {key}"


def test_assignment_status_lifecycle_enum() -> None:
    assert list(QuizAssignmentStatus) == [
        QuizAssignmentStatus.PENDING,
        QuizAssignmentStatus.PUBLISHED,
        QuizAssignmentStatus.ATTEMPTED,
        QuizAssignmentStatus.COMPLETED,
    ]
    col = SchoolQuizAssignment.__table__.columns["status"]
    assert isinstance(col.type, SAEnum)
    assert set(col.type.enums) == {"pending", "published", "attempted", "completed"}


def test_quiz_status_and_difficulty_enums() -> None:
    assert set(QuizStatus) == {
        QuizStatus.REQUESTED,
        QuizStatus.GENERATING,
        QuizStatus.READY,
        QuizStatus.FAILED,
    }
    assert set(QuizQuestionDifficulty) == {
        QuizQuestionDifficulty.FOUNDATIONAL,
        QuizQuestionDifficulty.CONCEPTUAL,
        QuizQuestionDifficulty.APPLIED,
        QuizQuestionDifficulty.GRADE_DEFAULT,
    }


def test_questions_carry_difficulty_and_source_metadata() -> None:
    col_diff = SchoolQuizQuestion.__table__.columns["difficulty"]
    col_src = SchoolQuizQuestion.__table__.columns["source_metadata_jsonb"]
    assert isinstance(col_diff.type, SAEnum)
    assert col_src.nullable is False


def test_calibration_jsonb_records_seed_inputs() -> None:
    profile = CalibrationProfile(
        source=CalibrationSource.DIAGNOSTIC_SEED,
        topic_confidence={"newton": 0.9},
        focus_areas=["optics"],
        target_difficulty="applied",
    )
    blob = profile.to_jsonb()
    restored = CalibrationProfile.from_jsonb(blob)
    assert restored.source == CalibrationSource.DIAGNOSTIC_SEED
    assert restored.topic_confidence["newton"] == 0.9
    assert restored.target_difficulty == "applied"


def test_grade_default_calibration_when_no_seed() -> None:
    profile = CalibrationProfile(
        source=CalibrationSource.GRADE_DEFAULT,
        target_difficulty="grade_default",
    )
    assert profile.to_jsonb()["source"] == "grade_default"


def test_per_student_unique_on_lecture_version() -> None:
    table = cast(Table, SchoolQuiz.__table__)
    names = {c.name for c in table.constraints if isinstance(c, UniqueConstraint)}
    assert "quizzes_lecture_version_student_uq" in names


def test_attempt_one_per_assignment_and_score_checks() -> None:
    table = cast(Table, SchoolQuizAttempt.__table__)
    uq = {c.name for c in table.constraints if isinstance(c, UniqueConstraint)}
    checks = {c.name for c in table.constraints if isinstance(c, CheckConstraint)}
    assert "quiz_attempts_assignment_uq" in uq
    assert "quiz_attempts_score_lte_max_check" in checks


def test_independent_tables_exist_but_documented_never_auto_populated() -> None:
    assert IndependentQuiz.__table__.schema == "independent"
    assert IndependentQuizQuestion.__table__.schema == "independent"
    assert IndependentQuizAssignment.__table__.schema == "independent"
    assert IndependentQuizAttempt.__table__.schema == "independent"
    source = Path(quiz_models.__file__).read_text(encoding="utf-8")
    assert "never auto-populated" in source.lower() or "never populate" in source.lower()


def test_migrations_exist_for_both_schemas() -> None:
    assert _SCHOOL_MIGRATION.is_file()
    assert _INDEPENDENT_MIGRATION.is_file()
    school_src = _SCHOOL_MIGRATION.read_text(encoding="utf-8")
    assert "school_0065" in school_src
    assert "down_revision: str = \"school_0064\"" in school_src
    ind_src = _INDEPENDENT_MIGRATION.read_text(encoding="utf-8")
    assert "independent_0018" in ind_src


def test_school_row_defaults() -> None:
    quiz = SchoolQuiz(
        lecture_id="lec-1",
        lecture_version_id="ver-1",
        student_user_id="stu-1",
    )
    assert quiz.tenant_type == QuizTenantType.SCHOOL
    assert quiz.status == QuizStatus.REQUESTED

    now = datetime.now(timezone.utc)
    assignment = SchoolQuizAssignment(
        quiz_id=quiz.id,
        student_user_id="stu-1",
        assigned_at=now,
        calibration_jsonb=CalibrationProfile(
            source=CalibrationSource.GRADE_DEFAULT,
            target_difficulty="grade_default",
        ).to_jsonb(),
    )
    assert assignment.status == QuizAssignmentStatus.PENDING


def test_options_and_source_metadata_round_trip() -> None:
    options = QuizOptionsList(
        options=[
            QuizQuestionOption(key="a", text="Force"),
            QuizQuestionOption(key="b", text="Mass"),
        ]
    )
    assert options.to_jsonb()[0]["key"] == "a"
    meta = QuestionSourceMetadata(
        lecture_id="lec-1",
        lecture_version_id="ver-1",
        paragraph_ordinal=2,
        excerpt="Newton's second law…",
        tier="lecture_body",
    )
    assert QuestionSourceMetadata.from_jsonb(meta.to_jsonb()).paragraph_ordinal == 2


def test_answers_map_accepts_flat_dict() -> None:
    mapped = QuizAnswersMap.from_jsonb({"q1": "a", "q2": "b"})
    assert mapped.answers == {"q1": "a", "q2": "b"}


def test_options_reject_single_choice() -> None:
    with pytest.raises(ValidationError):
        QuizOptionsList(options=[QuizQuestionOption(key="a", text="only")])


def test_foreign_keys_declare_ondelete() -> None:
    for table in (
        SchoolQuiz.__table__,
        SchoolQuizQuestion.__table__,
        SchoolQuizAssignment.__table__,
        SchoolQuizAttempt.__table__,
    ):
        for fk in table.foreign_keys:
            assert fk.ondelete is not None, f"{table}.{fk.parent} missing ondelete"
