"""School: student_goals.achievement_check_at (T-211).

Revision ID: school_0083
Revises: school_0082
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "school_0083"
down_revision: str = "school_0082"
branch_labels: tuple[()] = ()
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "student_goals",
        sa.Column("achievement_check_at", sa.DateTime(timezone=True), nullable=True),
        schema="school",
    )


def downgrade() -> None:
    op.drop_column("student_goals", "achievement_check_at", schema="school")
