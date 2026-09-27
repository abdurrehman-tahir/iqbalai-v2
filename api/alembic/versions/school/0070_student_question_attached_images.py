"""Add attached_images_jsonb to student_questions + conversations (T-169).

Revision ID: school_0070
Revises: school_0069
Create Date: 2026-09-26

Purpose: Flow 6 §3.5 image-bearing questions — store up to 3 image refs
(``AttachedImageRef``: storage_key/mime_type/size_bytes/upload_id) per
question and, for multi-turn follow-ups, per user conversation turn. Refs
point at MinIO objects already ingested via the T-166
``student_question_image`` upload profile; this migration only adds the
JSONB pointer columns.

Risk: low — additive nullable JSONB columns only.
Reversible: yes
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "school_0070"
down_revision: str = "school_0069"
branch_labels: tuple[()] = ()
depends_on: str | None = None

_SCHEMA = "school"


def upgrade() -> None:
    op.add_column(
        "student_questions",
        sa.Column("attached_images_jsonb", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        schema=_SCHEMA,
    )
    op.add_column(
        "student_question_conversations",
        sa.Column("attached_images_jsonb", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        schema=_SCHEMA,
    )


def downgrade() -> None:
    op.drop_column("student_question_conversations", "attached_images_jsonb", schema=_SCHEMA)
    op.drop_column("student_questions", "attached_images_jsonb", schema=_SCHEMA)
