"""School migration: student questions + conversations (T-156 / T-160).

Revision ID: school_0068
Revises: school_0067
Create Date: 2026-09-21

Purpose: student_questions + student_question_conversations (school) —
Flow 6 §3.3 highlight→Q submit and §3.4 multi-turn threads.
Independent schema deferred (Flow 8 self-study).
Risk: low — additive tables + enums only.
Reversible: yes
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "school_0068"
down_revision: str = "school_0067"
branch_labels: tuple[()] = ()
depends_on: str | None = None

_SCHEMA = "school"
_CLASSIFICATION_VALUES = ("misconception", "knowledge_gap", "unclassified")
_ROLE_VALUES = ("user", "assistant")


def _create_enum_if_missing(qualified_name: str, values_sql: str) -> None:
    op.execute(
        f"""
        DO $$ BEGIN
            CREATE TYPE {qualified_name} AS ENUM ({values_sql});
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$;
        """
    )


def upgrade() -> None:
    conn = op.get_bind()
    if conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = :schema AND table_name = 'student_questions'"
        ),
        {"schema": _SCHEMA},
    ).scalar():
        return

    _create_enum_if_missing(
        f"{_SCHEMA}.student_questions_classification_enum",
        ", ".join(f"'{v}'" for v in _CLASSIFICATION_VALUES),
    )
    _create_enum_if_missing(
        f"{_SCHEMA}.student_question_conversations_role_enum",
        ", ".join(f"'{v}'" for v in _ROLE_VALUES),
    )

    classification_enum = postgresql.ENUM(
        *_CLASSIFICATION_VALUES,
        name="student_questions_classification_enum",
        schema=_SCHEMA,
        create_type=False,
    )
    role_enum = postgresql.ENUM(
        *_ROLE_VALUES,
        name="student_question_conversations_role_enum",
        schema=_SCHEMA,
        create_type=False,
    )
    # Reuse lectures_tenant_type_enum created by school_0051 — do not CREATE TYPE.
    tenant_type_enum = postgresql.ENUM(
        "school",
        "independent",
        name="lectures_tenant_type_enum",
        schema=_SCHEMA,
        create_type=False,
    )

    op.create_table(
        "student_questions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "student_user_id",
            sa.String(36),
            sa.ForeignKey(f"{_SCHEMA}.users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "session_id",
            sa.String(36),
            sa.ForeignKey(f"{_SCHEMA}.lecture_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "lecture_id",
            sa.String(36),
            sa.ForeignKey(f"{_SCHEMA}.lectures.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tenant_type", tenant_type_enum, nullable=False, server_default="school"),
        sa.Column("highlight_text", sa.Text(), nullable=True),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("question_language", sa.String(8), nullable=False, server_default="en"),
        sa.Column(
            "paragraph_id",
            sa.String(36),
            sa.ForeignKey(f"{_SCHEMA}.lecture_paragraphs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("source_chunk_id", sa.String(128), nullable=True),
        sa.Column(
            "classification",
            classification_enum,
            nullable=False,
            server_default="unclassified",
        ),
        sa.Column("answer_text", sa.Text(), nullable=True),
        sa.Column("answer_source_tags_jsonb", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("asked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_student_questions_lecture_id",
        "student_questions",
        ["lecture_id"],
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_student_questions_session_id",
        "student_questions",
        ["session_id"],
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_student_questions_student_user_id",
        "student_questions",
        ["student_user_id"],
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_student_questions_paragraph_id",
        "student_questions",
        ["paragraph_id"],
        schema=_SCHEMA,
    )

    op.create_table(
        "student_question_conversations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "root_question_id",
            sa.String(36),
            sa.ForeignKey(f"{_SCHEMA}.student_questions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("turn_index", sa.Integer(), nullable=False),
        sa.Column("role", role_enum, nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("source_tags_jsonb", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "root_question_id",
            "turn_index",
            name="student_question_conversations_root_turn_uq",
        ),
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_student_question_conversations_root_question_id",
        "student_question_conversations",
        ["root_question_id"],
        schema=_SCHEMA,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_student_question_conversations_root_question_id",
        table_name="student_question_conversations",
        schema=_SCHEMA,
    )
    op.drop_table("student_question_conversations", schema=_SCHEMA)
    op.drop_index(
        "ix_student_questions_paragraph_id",
        table_name="student_questions",
        schema=_SCHEMA,
    )
    op.drop_index(
        "ix_student_questions_student_user_id",
        table_name="student_questions",
        schema=_SCHEMA,
    )
    op.drop_index(
        "ix_student_questions_session_id",
        table_name="student_questions",
        schema=_SCHEMA,
    )
    op.drop_index(
        "ix_student_questions_lecture_id",
        table_name="student_questions",
        schema=_SCHEMA,
    )
    op.drop_table("student_questions", schema=_SCHEMA)
    op.execute(f"DROP TYPE IF EXISTS {_SCHEMA}.student_question_conversations_role_enum")
    op.execute(f"DROP TYPE IF EXISTS {_SCHEMA}.student_questions_classification_enum")
