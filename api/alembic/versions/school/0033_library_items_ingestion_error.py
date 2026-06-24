"""library_items.ingestion_error — T-061.

Revision ID: school_0033
Revises: school_0032
Create Date: 2026-06-16

Purpose: Store terminal ingestion failure reason for school library items.
Risk: low
Reversible: yes
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "school_0033"
down_revision: str = "school_0032"
branch_labels: tuple[()] = ()
depends_on: str | None = None


def upgrade() -> None:
    conn = op.get_bind()
    if conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema = 'school' AND table_name = 'library_items' "
            "AND column_name = 'ingestion_error'"
        )
    ).scalar():
        return

    op.add_column(
        "library_items",
        sa.Column("ingestion_error", sa.Text(), nullable=True),
        schema="school",
    )


def downgrade() -> None:
    op.drop_column("library_items", "ingestion_error", schema="school")
