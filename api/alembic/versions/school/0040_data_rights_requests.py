"""Add data_rights_requests table for export and deletion requests.

Revision ID: school_0040
Revises: school_0039
Create Date: 2026-06-22

T-084 (M-06): PDPB-aligned data export + deletion request capture (Flow 4 §3.8).

Purpose: data_rights_requests table for export/deletion lifecycle.
Risk: low
Reversible: yes
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "school_0040"
down_revision: str = "school_0039"
branch_labels: tuple[()] = ()
depends_on: str | None = None


def upgrade() -> None:
    conn = op.get_bind()
    if conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = 'school' AND table_name = 'data_rights_requests'"
        )
    ).scalar():
        return

    op.execute(
        "CREATE TYPE school.data_rights_request_type AS ENUM ('export', 'deletion')"
    )
    op.execute(
        "CREATE TYPE school.data_rights_request_status AS ENUM ("
        "'requested', 'processing', 'ready', 'expired', "
        "'grace_period', 'cancelled', 'completed'"
        ")"
    )

    request_type = postgresql.ENUM(
        "export",
        "deletion",
        name="data_rights_request_type",
        schema="school",
        create_type=False,
    )
    request_status = postgresql.ENUM(
        "requested",
        "processing",
        "ready",
        "expired",
        "grace_period",
        "cancelled",
        "completed",
        name="data_rights_request_status",
        schema="school",
        create_type=False,
    )

    op.create_table(
        "data_rights_requests",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("school.users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("request_type", request_type, nullable=False),
        sa.Column("status", request_status, nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ready_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deletion_scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("file_key", sa.String(512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        schema="school",
    )
    op.create_index(
        "ix_data_rights_requests_user_id",
        "data_rights_requests",
        ["user_id"],
        schema="school",
    )
    op.create_index(
        "ix_data_rights_requests_status",
        "data_rights_requests",
        ["status"],
        schema="school",
    )


def downgrade() -> None:
    op.drop_index("ix_data_rights_requests_status", table_name="data_rights_requests", schema="school")
    op.drop_index("ix_data_rights_requests_user_id", table_name="data_rights_requests", schema="school")
    op.drop_table("data_rights_requests", schema="school")
    op.execute("DROP TYPE IF EXISTS school.data_rights_request_status")
    op.execute("DROP TYPE IF EXISTS school.data_rights_request_type")
