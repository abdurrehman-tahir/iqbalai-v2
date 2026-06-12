"""Add region and language_preference to school.districts.

Revision ID: school_0013
Revises: school_0012
Create Date: 2026-06-12

T-029 (M-02 School Onboarding): Platform Admin captures optional district metadata
(region + language preference) at creation time (flow-2 §3.1). Both columns are
nullable — they are descriptive, not structural. `language_preference` is a short
locale/language code kept as a plain string (no editable reference table at this
stage); see the model docstring for the rationale.

These columns live on a tenant-root table (`districts`) which carries no RLS per
ARCH §3.3 — nothing about RLS changes here.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "school_0013"
down_revision: str = "school_0012"
branch_labels: tuple[()] = ()
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "districts",
        sa.Column("region", sa.String(200), nullable=True),
        schema="school",
    )
    op.add_column(
        "districts",
        sa.Column("language_preference", sa.String(20), nullable=True),
        schema="school",
    )


def downgrade() -> None:
    op.drop_column("districts", "language_preference", schema="school")
    op.drop_column("districts", "region", schema="school")
