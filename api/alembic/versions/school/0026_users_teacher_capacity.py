"""Add teacher_capacity column to users table.

Revision ID: school_0026
Revises: school_0025
Create Date: 2026-06-15

T-046 (M-03): teacher Grade-Subject assignment capacity (default 5, range 1-20).

Purpose: Enforce teacher assignment caps per flow-3 §3.5.
Risk: low
Reversible: yes
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "school_0026"
down_revision: str = "school_0025"
branch_labels: tuple[()] = ()
depends_on: str | None = None


def upgrade() -> None:
    conn = op.get_bind()
    if conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema = 'school' AND table_name = 'users' "
            "AND column_name = 'teacher_capacity'"
        )
    ).scalar():
        return

    op.add_column(
        "users",
        sa.Column("teacher_capacity", sa.Integer(), nullable=False, server_default="5"),
        schema="school",
    )


def downgrade() -> None:
    op.drop_column("users", "teacher_capacity", schema="school")
