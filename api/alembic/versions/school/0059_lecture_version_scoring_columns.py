"""School migration: topic_relevance_pct/originality_score/edit_summary on
lecture_versions (T-129, Flow 5 §3.5-3.7).

Revision ID: school_0059
Revises: school_0058
Create Date: 2026-09-11

Purpose: three nullable columns feeding T-135 (originality), T-136 (topic
relevance) and T-130 (editor-derived edit_summary). scores_jsonb already
exists (school_0051) and needs no change here.
Risk: low — additive nullable columns only.
Reversible: yes
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "school_0059"
down_revision: str = "school_0058"
branch_labels: tuple[()] = ()
depends_on: str | None = None

_SCHEMA = "school"


def upgrade() -> None:
    op.add_column(
        "lecture_versions",
        sa.Column("topic_relevance_pct", sa.Numeric(5, 2), nullable=True),
        schema=_SCHEMA,
    )
    op.add_column(
        "lecture_versions",
        sa.Column("originality_score", sa.Numeric(4, 3), nullable=True),
        schema=_SCHEMA,
    )
    op.add_column(
        "lecture_versions",
        sa.Column(
            "edit_summary", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        schema=_SCHEMA,
    )


def downgrade() -> None:
    op.drop_column("lecture_versions", "edit_summary", schema=_SCHEMA)
    op.drop_column("lecture_versions", "originality_score", schema=_SCHEMA)
    op.drop_column("lecture_versions", "topic_relevance_pct", schema=_SCHEMA)
