"""Add platform_reference_books table (T-024).

Platform Library: globally-scoped reference books uploaded by Platform Admin.
Cross-schema read-only view for independent tenant per ARCH §3.16.

Revision ID: school_0010
Revises: school_0009
Create Date: 2026-05-26


Purpose: Add platform reference books table for M-01 library.
Risk: low
Reversible: yes
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "school_0010"
down_revision: str = "school_0009"
branch_labels: tuple[()] = ()
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "platform_reference_books",
        sa.Column("id", sa.String(36), primary_key=True),
        # FK to upload_records.id — the raw file record
        sa.Column("upload_id", sa.String(36), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        # curriculum | reference
        sa.Column("content_type", sa.String(20), nullable=False, server_default="reference"),
        # Optional link to exam_syllabi.id for filtering in RAG
        sa.Column("subject_tag", sa.String(255), nullable=True),
        sa.Column("grade_range_min", sa.Integer, nullable=True),
        sa.Column("grade_range_max", sa.Integer, nullable=True),
        # ISO 639-1 code (en | ur | sd | ps)
        sa.Column("language", sa.String(10), nullable=False, server_default="en"),
        # SHA-256 of file bytes — global dedup key
        sa.Column("sha256", sa.String(64), nullable=False),
        # processing | available | ingestion_failed
        sa.Column("status", sa.String(30), nullable=False, server_default="processing"),
        # Qdrant collection this book's chunks are stored in
        sa.Column(
            "qdrant_collection", sa.String(100), nullable=False, server_default="platform_chunks"
        ),
        # Number of chunks written to Qdrant (populated post-ingestion)
        sa.Column("chunk_count", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        schema="school",
    )
    op.create_index(
        "ix_platform_reference_books_sha256",
        "platform_reference_books",
        ["sha256"],
        schema="school",
    )
    op.create_index(
        "ix_platform_reference_books_status",
        "platform_reference_books",
        ["status"],
        schema="school",
    )
    op.create_index(
        "ix_platform_reference_books_language",
        "platform_reference_books",
        ["language"],
        schema="school",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_platform_reference_books_language",
        table_name="platform_reference_books",
        schema="school",
    )
    op.drop_index(
        "ix_platform_reference_books_status",
        table_name="platform_reference_books",
        schema="school",
    )
    op.drop_index(
        "ix_platform_reference_books_sha256",
        table_name="platform_reference_books",
        schema="school",
    )
    op.drop_table("platform_reference_books", schema="school")
