"""Add bulk_imports table for coordinator dry-run imports.

Revision ID: school_0019
Revises: school_0018
Create Date: 2026-06-12

T-037 (M-02): bulk import skeleton per flow-2 §10.

Purpose: Add bulk_imports table for coordinator CSV dry-run imports.
Risk: low
Reversible: yes
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision: str = "school_0019"
down_revision: str = "school_0018"
branch_labels: tuple[()] = ()
depends_on: str | None = None


def upgrade() -> None:
    conn = op.get_bind()
    if conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = 'school' AND table_name = 'bulk_imports'"
        )
    ).scalar():
        return

    op.create_table(
        "bulk_imports",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("school_id", sa.String(36), nullable=False),
        sa.Column("imported_by_user_id", sa.String(36), nullable=False),
        sa.Column("upload_id", sa.String(36), nullable=False),
        sa.Column("total_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("success_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_report_jsonb", JSONB, nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "dry_run_complete",
                name="bulkimportstatus",
                schema="school",
                create_type=True,
            ),
            nullable=False,
            server_default="dry_run_complete",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        schema="school",
    )
    op.create_index(
        "ix_bulk_imports_school_id",
        "bulk_imports",
        ["school_id"],
        schema="school",
    )


def downgrade() -> None:
    op.drop_index("ix_bulk_imports_school_id", table_name="bulk_imports", schema="school")
    op.drop_table("bulk_imports", schema="school")
    op.execute("DROP TYPE IF EXISTS school.bulkimportstatus")
