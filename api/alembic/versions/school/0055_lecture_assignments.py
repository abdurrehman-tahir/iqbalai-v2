"""School migration: lecture_assignments table (T-123, #21).

Revision ID: school_0055
Revises: school_0054
Create Date: 2026-08-05

Purpose: lecture_assignments (school) — per-lecture access restriction to
specific students or sections; default (no rows) is all-enrolled-students
(flow-5 §3.14).
Risk: low — additive table only.
Reversible: yes
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "school_0055"
down_revision: str = "school_0054"
branch_labels: tuple[()] = ()
depends_on: str | None = None

_SCHEMA = "school"
_SCOPE_VALUES = ("student", "section")


def _create_enum_if_missing(qualified_name: str, values_sql: str) -> None:
    # Idempotent CREATE TYPE — never emit CREATE TYPE via sa.Enum create_table
    # (AUDIT_LOG [migration-enum-create]).
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
    scope_list = ", ".join(f"'{v}'" for v in _SCOPE_VALUES)
    _create_enum_if_missing(f"{_SCHEMA}.lecture_assignments_scope_enum", scope_list)

    scope_enum = postgresql.ENUM(
        *_SCOPE_VALUES,
        name="lecture_assignments_scope_enum",
        schema=_SCHEMA,
        create_type=False,
    )

    op.create_table(
        "lecture_assignments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "lecture_id",
            sa.String(36),
            sa.ForeignKey(f"{_SCHEMA}.lectures.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("scope", scope_enum, nullable=False),
        sa.Column(
            "student_user_id",
            sa.String(36),
            sa.ForeignKey(f"{_SCHEMA}.users.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "section_id",
            sa.String(36),
            sa.ForeignKey(f"{_SCHEMA}.sections.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "created_by_user_id",
            sa.String(36),
            sa.ForeignKey(f"{_SCHEMA}.users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "(scope = 'student' AND student_user_id IS NOT NULL AND section_id IS NULL) OR "
            "(scope = 'section' AND section_id IS NOT NULL AND student_user_id IS NULL)",
            name="lecture_assignments_scope_target_check",
        ),
        sa.UniqueConstraint(
            "lecture_id", "student_user_id", name="lecture_assignments_lecture_student_uq"
        ),
        sa.UniqueConstraint(
            "lecture_id", "section_id", name="lecture_assignments_lecture_section_uq"
        ),
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_lecture_assignments_lecture_id",
        "lecture_assignments",
        ["lecture_id"],
        schema=_SCHEMA,
    )


def downgrade() -> None:
    op.drop_table("lecture_assignments", schema=_SCHEMA)
    op.execute(f"DROP TYPE IF EXISTS {_SCHEMA}.lecture_assignments_scope_enum")
