"""Add index on grades.promoted_from_grade_id FK column.

Revision ID: school_0028
Revises: school_0027
Create Date: 2026-06-16

ARCH §4 requires every foreign-key column to be indexed (T-230 model-metadata lint).

Purpose: Index self-referential promotion FK on grades.
Risk: low
Reversible: yes
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "school_0028"
down_revision: str = "school_0027"
branch_labels: tuple[()] = ()
depends_on: str | None = None


def upgrade() -> None:
    conn = op.get_bind()
    if conn.execute(
        sa.text(
            "SELECT 1 FROM pg_indexes "
            "WHERE schemaname = 'school' AND tablename = 'grades' "
            "AND indexname = 'ix_grades_promoted_from_grade_id'"
        )
    ).scalar():
        return

    op.create_index(
        "ix_grades_promoted_from_grade_id",
        "grades",
        ["promoted_from_grade_id"],
        schema="school",
    )


def downgrade() -> None:
    op.drop_index("ix_grades_promoted_from_grade_id", table_name="grades", schema="school")
