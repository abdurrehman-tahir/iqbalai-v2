"""Initial independent schema migration.

Revision ID: independent_0001
Revises:
Create Date: 2026-05-20

"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "independent_0001"
down_revision: str | None = None
branch_labels: tuple[str, ...] = ("independent",)
depends_on: str | None = None


def upgrade() -> None:
    """Create independent schema (handled by init.sql, registered here for Alembic tracking)."""
    op.execute("CREATE SCHEMA IF NOT EXISTS independent")


def downgrade() -> None:
    """Drop independent schema."""
    # WARNING: This drops all tables in the independent schema.
    op.execute("DROP SCHEMA IF EXISTS independent CASCADE")
