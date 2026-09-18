"""Independent migration: content_jsonb on lecture_versions (T-130, STACK_LOCK §2).

Revision ID: independent_0017
Revises: independent_0016
Create Date: 2026-09-11

Purpose: mirrors school_0063 for the independent schema.
Risk: low — additive nullable column only.
Reversible: yes
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "independent_0017"
down_revision: str = "independent_0016"
branch_labels: tuple[()] = ()
depends_on: str | None = None

_SCHEMA = "independent"


def upgrade() -> None:
    op.add_column(
        "lecture_versions",
        sa.Column("content_jsonb", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        schema=_SCHEMA,
    )


def downgrade() -> None:
    op.drop_column("lecture_versions", "content_jsonb", schema=_SCHEMA)
