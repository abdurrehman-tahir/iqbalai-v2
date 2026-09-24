"""T-156/T-160 — student_questions model + migration shape tests (offline)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import Enum as SAEnum
from sqlalchemy import Table

from app.db.base import Base, SoftDeleteMixin
from app.features.student_questions.models import (
    ConversationRole,
    QuestionClassification,
    SchoolStudentQuestion,
    SchoolStudentQuestionConversation,
    StudentQuestionTenantType,
)

_SCHOOL_MIGRATION = (
    Path(__file__).resolve().parents[4]
    / "alembic"
    / "versions"
    / "school"
    / "0068_student_questions.py"
)


def test_student_questions_tables_registered_school_only() -> None:
    assert "school.student_questions" in Base.metadata.tables
    assert "school.student_question_conversations" in Base.metadata.tables
    assert "independent.student_questions" not in Base.metadata.tables
    assert "independent.student_question_conversations" not in Base.metadata.tables


def test_student_question_has_no_soft_delete() -> None:
    assert not issubclass(SchoolStudentQuestion, SoftDeleteMixin)
    assert not issubclass(SchoolStudentQuestionConversation, SoftDeleteMixin)


def test_student_question_columns_and_enums() -> None:
    table = Base.metadata.tables["school.student_questions"]
    assert isinstance(table, Table)
    cols = {c.name for c in table.columns}
    assert {
        "id",
        "student_user_id",
        "session_id",
        "lecture_id",
        "tenant_type",
        "highlight_text",
        "question_text",
        "question_language",
        "paragraph_id",
        "source_chunk_id",
        "classification",
        "answer_text",
        "answer_source_tags_jsonb",
        "asked_at",
        "answered_at",
        "created_at",
        "updated_at",
    } <= cols

    classification_col = table.c.classification.type
    assert isinstance(classification_col, SAEnum)
    assert set(classification_col.enums) == {c.value for c in QuestionClassification}


def test_conversation_columns_and_role_enum() -> None:
    table = Base.metadata.tables["school.student_question_conversations"]
    assert isinstance(table, Table)
    cols = {c.name for c in table.columns}
    assert {
        "id",
        "root_question_id",
        "turn_index",
        "role",
        "content",
        "source_tags_jsonb",
        "created_at",
        "updated_at",
    } <= cols

    role_col = table.c.role.type
    assert isinstance(role_col, SAEnum)
    assert set(role_col.enums) == {r.value for r in ConversationRole}


def test_question_defaults() -> None:
    now = datetime.now(timezone.utc)
    row = SchoolStudentQuestion(
        student_user_id="stu-1",
        session_id="sess-1",
        lecture_id="lec-1",
        question_text="Explain: gravity",
        asked_at=now,
    )
    assert row.tenant_type == StudentQuestionTenantType.SCHOOL
    assert row.classification == QuestionClassification.UNCLASSIFIED
    assert row.question_language == "en"
    assert row.id


def test_migration_file_exists_and_revises_audio_caches() -> None:
    text = _SCHOOL_MIGRATION.read_text(encoding="utf-8")
    assert 'revision: str = "school_0068"' in text
    assert 'down_revision: str = "school_0067"' in text
    assert "student_questions" in text
    assert "student_question_conversations" in text
    assert "Flow 8" in text
