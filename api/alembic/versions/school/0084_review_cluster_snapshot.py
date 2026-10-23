"""School migration: review card cluster snapshot + timing columns (T-200, Flow 7 §3.1).

Revision ID: school_0084
Revises: school_0080
Create Date: 2026-10-23

Purpose: lecture_reviews.clusters_jsonb (classified-cluster snapshot the card,
drill-down and targeted distribution read), generated_at (05:00 SLA check),
notified_at (idempotent 06:00 teacher notification) and acted_at (first
action on the card — "days to act" on the admin dashboard, T-206).
Risk: low — additive columns; clusters_jsonb has a server default so existing
rows backfill to ``[]``.
Reversible: yes

Numbered 0084 (not 0081) because the open M-17 branch already owns
school_0081–0083; whichever milestone merges second re-points down_revision at
the other's head.

Hand-authored to match LectureReview (model-first; no DB available for
autogenerate in this session — columns mirror the model exactly).
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "school_0084"
down_revision: str = "school_0080"
branch_labels: tuple[()] = ()
depends_on: str | None = None

_SCHEMA = "school"
_TABLE = "lecture_reviews"


def upgrade() -> None:
    op.add_column(
        _TABLE,
        sa.Column(
            "clusters_jsonb",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        schema=_SCHEMA,
    )
    op.add_column(
        _TABLE,
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True),
        schema=_SCHEMA,
    )
    op.add_column(
        _TABLE,
        sa.Column("notified_at", sa.DateTime(timezone=True), nullable=True),
        schema=_SCHEMA,
    )
    op.add_column(
        _TABLE,
        sa.Column("acted_at", sa.DateTime(timezone=True), nullable=True),
        schema=_SCHEMA,
    )


def downgrade() -> None:
    op.drop_column(_TABLE, "acted_at", schema=_SCHEMA)
    op.drop_column(_TABLE, "notified_at", schema=_SCHEMA)
    op.drop_column(_TABLE, "generated_at", schema=_SCHEMA)
    op.drop_column(_TABLE, "clusters_jsonb", schema=_SCHEMA)
