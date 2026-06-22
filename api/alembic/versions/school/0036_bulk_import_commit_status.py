"""Extend bulk import status enum for commit results.

Revision ID: school_0036
Revises: school_0035
Create Date: 2026-06-22

T-079 (M-06): committed + committed_with_errors bulk import states.

Purpose: Add commit lifecycle values to bulkimportstatus enum.
Risk: low
Reversible: yes
"""

from __future__ import annotations

from alembic import op

revision: str = "school_0036"
down_revision: str = "school_0035"
branch_labels: tuple[()] = ()
depends_on: str | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE school.bulkimportstatus ADD VALUE IF NOT EXISTS 'committed'")
    op.execute(
        "ALTER TYPE school.bulkimportstatus ADD VALUE IF NOT EXISTS 'committed_with_errors'"
    )


def downgrade() -> None:
    pass
