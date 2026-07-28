"""Independent migration: diagnostics lifecycle table (T-103).

Revision ID: independent_0009
Revises: independent_0008
Create Date: 2026-07-28

Purpose: Independent-schema diagnostic attempts (per-framework scope).
Risk: low
Reversible: yes
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "independent_0009"
down_revision: str = "independent_0008"
branch_labels: tuple[()] = ()
depends_on: str | None = None


def upgrade() -> None:
    conn = op.get_bind()
    if conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = 'independent' AND table_name = 'diagnostics'"
        )
    ).scalar():
        return

    op.execute(
        "CREATE TYPE independent.diagnostics_status_enum AS ENUM "
        "('not_taken', 'in_progress', 'completed')"
    )
    op.execute(
        "CREATE TYPE independent.diagnostics_tenant_type_enum AS ENUM " "('school', 'independent')"
    )

    status = postgresql.ENUM(
        "not_taken",
        "in_progress",
        "completed",
        name="diagnostics_status_enum",
        schema="independent",
        create_type=False,
    )
    tenant_type = postgresql.ENUM(
        "school",
        "independent",
        name="diagnostics_tenant_type_enum",
        schema="independent",
        create_type=False,
    )

    op.create_table(
        "diagnostics",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_type", tenant_type, nullable=False),
        sa.Column(
            "student_user_id",
            sa.String(36),
            sa.ForeignKey("independent.users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("subject_id", sa.String(36), nullable=True),
        sa.Column("framework_id", sa.String(36), nullable=True),
        sa.Column("status", status, nullable=False),
        sa.Column(
            "questions_jsonb",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "answers_jsonb",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        schema="independent",
    )
    op.create_index(
        "ix_diagnostics_student_user_id",
        "diagnostics",
        ["student_user_id"],
        schema="independent",
    )
    op.create_index(
        "ix_diagnostics_subject_id", "diagnostics", ["subject_id"], schema="independent"
    )
    op.create_index(
        "ix_diagnostics_framework_id",
        "diagnostics",
        ["framework_id"],
        schema="independent",
    )
    op.create_index(
        "ix_diagnostics_deleted_at", "diagnostics", ["deleted_at"], schema="independent"
    )


def downgrade() -> None:
    op.drop_index("ix_diagnostics_deleted_at", table_name="diagnostics", schema="independent")
    op.drop_index("ix_diagnostics_framework_id", table_name="diagnostics", schema="independent")
    op.drop_index("ix_diagnostics_subject_id", table_name="diagnostics", schema="independent")
    op.drop_index("ix_diagnostics_student_user_id", table_name="diagnostics", schema="independent")
    op.drop_table("diagnostics", schema="independent")
    op.execute("DROP TYPE IF EXISTS independent.diagnostics_tenant_type_enum")
    op.execute("DROP TYPE IF EXISTS independent.diagnostics_status_enum")
