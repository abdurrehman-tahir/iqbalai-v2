"""Independent migration: retake_available_notified_at on diagnostics (T-109).

Revision ID: independent_0011
Revises: independent_0010
Create Date: 2026-07-29

Purpose: Idempotent retake-available notification tracking for diagnostic sweep.
Risk: low
Reversible: yes
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "independent_0011"
down_revision: str = "independent_0010"
branch_labels: tuple[()] = ()
depends_on: str | None = None


def upgrade() -> None:
    conn = op.get_bind()
    exists = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema = 'independent' AND table_name = 'diagnostics' "
            "AND column_name = 'retake_available_notified_at'"
        )
    ).scalar()
    if exists:
        return
    op.add_column(
        "diagnostics",
        sa.Column("retake_available_notified_at", sa.DateTime(timezone=True), nullable=True),
        schema="independent",
    )


def downgrade() -> None:
    op.drop_column("diagnostics", "retake_available_notified_at", schema="independent")
