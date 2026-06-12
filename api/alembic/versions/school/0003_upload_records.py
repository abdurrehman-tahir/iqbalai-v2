"""Add upload_records table to school schema.

Revision ID: school_0003
Revises: school_0002
Create Date: 2026-05-20


Purpose: Add upload_records table for file upload pipeline tracking.
Risk: low
Reversible: yes
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "school_0003"
down_revision: str = "school_0002"
branch_labels: tuple[()] = ()
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "upload_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("profile", sa.String(100), nullable=False),
        sa.Column("filename", sa.String(500), nullable=False),
        sa.Column("size_bytes", sa.Integer, nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("minio_key", sa.String(1000), nullable=False),
        sa.Column("bucket", sa.String(255), nullable=False),
        sa.Column("school_id", sa.String(36), nullable=True),
        sa.Column("uploaded_by", sa.String(36), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="ready"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        schema="school",
    )
    op.create_index("ix_upload_records_sha256", "upload_records", ["sha256"], schema="school")
    op.create_index("ix_upload_records_school_id", "upload_records", ["school_id"], schema="school")


def downgrade() -> None:
    op.drop_index("ix_upload_records_school_id", table_name="upload_records", schema="school")
    op.drop_index("ix_upload_records_sha256", table_name="upload_records", schema="school")
    op.drop_table("upload_records", schema="school")
