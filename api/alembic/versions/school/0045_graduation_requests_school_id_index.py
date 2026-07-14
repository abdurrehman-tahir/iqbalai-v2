"""Add index on graduation_requests.school_id FK column.

Revision ID: school_0045
Revises: school_0044
Create Date: 2026-07-09

ARCH §4 requires every foreign-key column to be indexed (T-230 model-metadata lint).

Purpose: Index school_id on graduation_requests.
Risk: low
Reversible: yes
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "school_0045"
down_revision: str = "school_0044"
branch_labels: tuple[()] = ()
depends_on: str | None = None


def upgrade() -> None:
    conn = op.get_bind()
    if conn.execute(
        sa.text(
            "SELECT 1 FROM pg_indexes "
            "WHERE schemaname = 'school' AND tablename = 'graduation_requests' "
            "AND indexname = 'ix_graduation_requests_school_id'"
        )
    ).scalar():
        return

    op.create_index(
        "ix_graduation_requests_school_id",
        "graduation_requests",
        ["school_id"],
        schema="school",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_graduation_requests_school_id",
        table_name="graduation_requests",
        schema="school",
    )
