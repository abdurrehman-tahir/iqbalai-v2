"""Initial school schema migration.

Revision ID: school_0001
Revises:
Create Date: 2026-05-20

"""
from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "school_0001"
down_revision: str | None = None
branch_labels: tuple[str, ...] = ("school",)
depends_on: str | None = None


def upgrade() -> None:
    """Create school schema (handled by init.sql, but registered here for Alembic tracking)."""
    op.execute("CREATE SCHEMA IF NOT EXISTS school")


def downgrade() -> None:
    """Drop school schema."""
    # WARNING: This drops all tables in the school schema.
    op.execute("DROP SCHEMA IF EXISTS school CASCADE")
