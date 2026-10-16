"""Independent: student_goals.achievement_check_at (T-211).

Revision ID: independent_0023
Revises: independent_0022

Purpose: add student_goals.achievement_check_at for once/day EOD goal check.
Risk: low — additive nullable column.
Reversible: yes
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "independent_0023"
down_revision: str = "independent_0022"
branch_labels: tuple[()] = ()
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "student_goals",
        sa.Column("achievement_check_at", sa.DateTime(timezone=True), nullable=True),
        schema="independent",
    )


def downgrade() -> None:
    op.drop_column("student_goals", "achievement_check_at", schema="independent")
