"""Add academic_sessions table and school.active_academic_session (T-042).

Revision ID: school_0022
Revises: school_0021
Create Date: 2026-06-15

T-042 (M-03): lightweight academic session lookup per school. Exactly one session
may be is_active=true; the school's active_academic_session column mirrors the label.

Purpose: Academic session model for grade pinning.
Risk: low
Reversible: yes
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "school_0022"
down_revision: str = "school_0021"
branch_labels: tuple[()] = ()
depends_on: str | None = None


def upgrade() -> None:
    conn = op.get_bind()
    if conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = 'school' AND table_name = 'academic_sessions'"
        )
    ).scalar():
        return

    op.add_column(
        "schools",
        sa.Column("active_academic_session", sa.String(50), nullable=True),
        schema="school",
    )

    op.create_table(
        "academic_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "school_id",
            sa.String(36),
            sa.ForeignKey("school.schools.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("label", sa.String(50), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        schema="school",
    )
    op.create_index(
        "academic_sessions_school_label_uq",
        "academic_sessions",
        ["school_id", "label"],
        unique=True,
        schema="school",
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_academic_sessions_school_id", "academic_sessions", ["school_id"], schema="school"
    )
    op.create_index(
        "ix_academic_sessions_deleted_at", "academic_sessions", ["deleted_at"], schema="school"
    )


def downgrade() -> None:
    op.drop_index(
        "ix_academic_sessions_deleted_at", table_name="academic_sessions", schema="school"
    )
    op.drop_index("ix_academic_sessions_school_id", table_name="academic_sessions", schema="school")
    op.drop_index(
        "academic_sessions_school_label_uq", table_name="academic_sessions", schema="school"
    )
    op.drop_table("academic_sessions", schema="school")
    op.drop_column("schools", "active_academic_session", schema="school")
