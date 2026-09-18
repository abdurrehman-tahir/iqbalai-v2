"""School migration: quiz tables (T-141).

Revision ID: school_0065
Revises: school_0064
Create Date: 2026-09-17

Purpose: quizzes / quiz_questions / quiz_assignments / quiz_attempts (school).
Risk: low — additive tables only; independent schema mirrored separately.
Reversible: yes
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "school_0065"
down_revision: str = "school_0064"
branch_labels: tuple[()] = ()
depends_on: str | None = None

_SCHEMA = "school"

_QUIZ_STATUS = ("requested", "generating", "ready", "failed")
_ASSIGNMENT_STATUS = ("pending", "published", "attempted", "completed")
_DIFFICULTY = ("foundational", "conceptual", "applied", "grade_default")


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
            "WHERE table_schema = :schema AND table_name = 'quizzes'"
        ),
        {"schema": _SCHEMA},
    ).scalar():
        return

    _create_enum_if_missing(
        f"{_SCHEMA}.quizzes_status_enum",
        ", ".join(f"'{v}'" for v in _QUIZ_STATUS),
    )
    _create_enum_if_missing(
        f"{_SCHEMA}.quiz_assignments_status_enum",
        ", ".join(f"'{v}'" for v in _ASSIGNMENT_STATUS),
    )
    _create_enum_if_missing(
        f"{_SCHEMA}.quiz_questions_difficulty_enum",
        ", ".join(f"'{v}'" for v in _DIFFICULTY),
    )
    _create_enum_if_missing(
        f"{_SCHEMA}.quizzes_tenant_type_enum",
        "'school', 'independent'",
    )

    quiz_status = postgresql.ENUM(
        *_QUIZ_STATUS,
        name="quizzes_status_enum",
        schema=_SCHEMA,
        create_type=False,
    )
    assignment_status = postgresql.ENUM(
        *_ASSIGNMENT_STATUS,
        name="quiz_assignments_status_enum",
        schema=_SCHEMA,
        create_type=False,
    )
    difficulty = postgresql.ENUM(
        *_DIFFICULTY,
        name="quiz_questions_difficulty_enum",
        schema=_SCHEMA,
        create_type=False,
    )
    tenant_type = postgresql.ENUM(
        "school",
        "independent",
        name="quizzes_tenant_type_enum",
        schema=_SCHEMA,
        create_type=False,
    )

    op.create_table(
        "quizzes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_type", tenant_type, nullable=False),
        sa.Column(
            "lecture_id",
            sa.String(36),
            sa.ForeignKey(f"{_SCHEMA}.lectures.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "lecture_version_id",
            sa.String(36),
            sa.ForeignKey(f"{_SCHEMA}.lecture_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "student_user_id",
            sa.String(36),
            sa.ForeignKey(f"{_SCHEMA}.users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", quiz_status, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "lecture_version_id",
            "student_user_id",
            name="quizzes_lecture_version_student_uq",
        ),
        schema=_SCHEMA,
    )
    op.create_index("ix_quizzes_lecture_id", "quizzes", ["lecture_id"], schema=_SCHEMA)
    op.create_index(
        "ix_quizzes_lecture_version_id", "quizzes", ["lecture_version_id"], schema=_SCHEMA
    )
    op.create_index("ix_quizzes_student_user_id", "quizzes", ["student_user_id"], schema=_SCHEMA)
    op.create_index("ix_quizzes_deleted_at", "quizzes", ["deleted_at"], schema=_SCHEMA)

    op.create_table(
        "quiz_questions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "quiz_id",
            sa.String(36),
            sa.ForeignKey(f"{_SCHEMA}.quizzes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("stem", sa.Text(), nullable=False),
        sa.Column(
            "options_jsonb",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("correct_answer", sa.String(16), nullable=False),
        sa.Column("difficulty", difficulty, nullable=False),
        sa.Column(
            "source_metadata_jsonb",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("quiz_id", "ordinal", name="quiz_questions_quiz_ordinal_uq"),
        sa.CheckConstraint("ordinal >= 1", name="quiz_questions_ordinal_positive_check"),
        schema=_SCHEMA,
    )
    op.create_index("ix_quiz_questions_quiz_id", "quiz_questions", ["quiz_id"], schema=_SCHEMA)
    op.create_index(
        "ix_quiz_questions_deleted_at", "quiz_questions", ["deleted_at"], schema=_SCHEMA
    )

    op.create_table(
        "quiz_assignments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "quiz_id",
            sa.String(36),
            sa.ForeignKey(f"{_SCHEMA}.quizzes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "student_user_id",
            sa.String(36),
            sa.ForeignKey(f"{_SCHEMA}.users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", assignment_status, nullable=False),
        sa.Column(
            "calibration_jsonb",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("quiz_id", "student_user_id", name="quiz_assignments_quiz_student_uq"),
        schema=_SCHEMA,
    )
    op.create_index("ix_quiz_assignments_quiz_id", "quiz_assignments", ["quiz_id"], schema=_SCHEMA)
    op.create_index(
        "ix_quiz_assignments_student_user_id",
        "quiz_assignments",
        ["student_user_id"],
        schema=_SCHEMA,
    )
    op.create_index("ix_quiz_assignments_status", "quiz_assignments", ["status"], schema=_SCHEMA)
    op.create_index(
        "ix_quiz_assignments_deleted_at",
        "quiz_assignments",
        ["deleted_at"],
        schema=_SCHEMA,
    )

    op.create_table(
        "quiz_attempts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "quiz_assignment_id",
            sa.String(36),
            sa.ForeignKey(f"{_SCHEMA}.quiz_assignments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "answers_jsonb",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("max_score", sa.Integer(), nullable=False),
        sa.Column("attempted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("quiz_assignment_id", name="quiz_attempts_assignment_uq"),
        sa.CheckConstraint("score >= 0", name="quiz_attempts_score_nonneg_check"),
        sa.CheckConstraint("max_score >= 1", name="quiz_attempts_max_score_positive_check"),
        sa.CheckConstraint("score <= max_score", name="quiz_attempts_score_le_max_check"),
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_quiz_attempts_quiz_assignment_id",
        "quiz_attempts",
        ["quiz_assignment_id"],
        schema=_SCHEMA,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_quiz_attempts_quiz_assignment_id",
        table_name="quiz_attempts",
        schema=_SCHEMA,
    )
    op.drop_table("quiz_attempts", schema=_SCHEMA)

    op.drop_index("ix_quiz_assignments_deleted_at", table_name="quiz_assignments", schema=_SCHEMA)
    op.drop_index("ix_quiz_assignments_status", table_name="quiz_assignments", schema=_SCHEMA)
    op.drop_index(
        "ix_quiz_assignments_student_user_id",
        table_name="quiz_assignments",
        schema=_SCHEMA,
    )
    op.drop_index("ix_quiz_assignments_quiz_id", table_name="quiz_assignments", schema=_SCHEMA)
    op.drop_table("quiz_assignments", schema=_SCHEMA)

    op.drop_index("ix_quiz_questions_deleted_at", table_name="quiz_questions", schema=_SCHEMA)
    op.drop_index("ix_quiz_questions_quiz_id", table_name="quiz_questions", schema=_SCHEMA)
    op.drop_table("quiz_questions", schema=_SCHEMA)

    op.drop_index("ix_quizzes_deleted_at", table_name="quizzes", schema=_SCHEMA)
    op.drop_index("ix_quizzes_student_user_id", table_name="quizzes", schema=_SCHEMA)
    op.drop_index("ix_quizzes_lecture_version_id", table_name="quizzes", schema=_SCHEMA)
    op.drop_index("ix_quizzes_lecture_id", table_name="quizzes", schema=_SCHEMA)
    op.drop_table("quizzes", schema=_SCHEMA)

    op.execute(f"DROP TYPE IF EXISTS {_SCHEMA}.quizzes_tenant_type_enum")
    op.execute(f"DROP TYPE IF EXISTS {_SCHEMA}.quiz_questions_difficulty_enum")
    op.execute(f"DROP TYPE IF EXISTS {_SCHEMA}.quiz_assignments_status_enum")
    op.execute(f"DROP TYPE IF EXISTS {_SCHEMA}.quizzes_status_enum")
