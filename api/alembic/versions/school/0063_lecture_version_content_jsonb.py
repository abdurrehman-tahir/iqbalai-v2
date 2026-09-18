"""School migration: content_jsonb on lecture_versions (T-130, STACK_LOCK §2).

Revision ID: school_0063
Revises: school_0062
Create Date: 2026-09-11

Purpose: STACK_LOCK's rich-text-editor row locks TipTap's JSON output into
``lecture_versions.content_jsonb`` — this column did not exist yet (T-129
only added the three scoring columns the ticket text named explicitly).
Nullable: v1 rows predate the editor (LLM-generated plain text/markdown in
``body`` only); every version created via T-130's save endpoint populates
both ``content_jsonb`` (TipTap source of truth) and ``body`` (plain-text
extraction, kept for scoring/embedding/RAG code paths that operate on text).
Risk: low — additive nullable column only.
Reversible: yes
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "school_0063"
down_revision: str = "school_0062"
branch_labels: tuple[()] = ()
depends_on: str | None = None

_SCHEMA = "school"


def upgrade() -> None:
    op.add_column(
        "lecture_versions",
        sa.Column("content_jsonb", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        schema=_SCHEMA,
    )


def downgrade() -> None:
    op.drop_column("lecture_versions", "content_jsonb", schema=_SCHEMA)
