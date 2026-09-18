"""School migration: teacher_tips_jsonb on lecture_versions (T-124, #28, #41).

Revision ID: school_0056
Revises: school_0055
Create Date: 2026-08-05

Purpose: adds a nullable teacher_tips_jsonb column to lecture_versions —
delivery tips + technique demo + real-world examples from a second,
general-knowledge-only LLM call fired after lecture generation.
Risk: low — additive nullable column only.
Reversible: yes
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "school_0056"
down_revision: str = "school_0055"
branch_labels: tuple[()] = ()
depends_on: str | None = None

_SCHEMA = "school"


def upgrade() -> None:
    op.add_column(
        "lecture_versions",
        sa.Column("teacher_tips_jsonb", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        schema=_SCHEMA,
    )


def downgrade() -> None:
    op.drop_column("lecture_versions", "teacher_tips_jsonb", schema=_SCHEMA)
