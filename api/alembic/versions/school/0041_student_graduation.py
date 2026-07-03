"""Add graduation fields and graduation workflow tables.

Revision ID: school_0041
Revises: school_0040
Create Date: 2026-06-22

T-085/T-086 (M-06): graduation lifecycle + migration log (Flow 4 §3.9).

Purpose: student_profiles graduation columns, graduation_requests, graduation_migration_log.
Risk: medium
Reversible: yes
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "school_0041"
down_revision: str = "school_0040"
branch_labels: tuple[()] = ()
depends_on: str | None = None


def upgrade() -> None:
    conn = op.get_bind()
    if conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema = 'school' AND table_name = 'student_profiles' "
            "AND column_name = 'is_graduated'"
        )
    ).scalar():
        return

    op.add_column(
        "student_profiles",
        sa.Column("is_graduated", sa.Boolean(), nullable=False, server_default="false"),
        schema="school",
    )
    op.add_column(
        "student_profiles",
        sa.Column("graduated_at", sa.DateTime(timezone=True), nullable=True),
        schema="school",
    )
    op.add_column(
        "student_profiles",
        sa.Column("migrated_out", sa.Boolean(), nullable=False, server_default="false"),
        schema="school",
    )
    op.add_column(
        "student_profiles",
        sa.Column("migrated_at", sa.DateTime(timezone=True), nullable=True),
        schema="school",
    )
    op.add_column(
        "student_profiles",
        sa.Column("migration_reminder_sent_days", sa.String(32), nullable=True),
        schema="school",
    )

    op.execute(
        "CREATE TYPE school.graduation_request_status AS ENUM ('pending', 'approved', 'rejected')"
    )
    op.execute(
        "CREATE TYPE school.graduation_migration_status AS ENUM ("
        "'pending', 'in_progress', 'succeeded', 'failed'"
        ")"
    )

    request_status = postgresql.ENUM(
        "pending",
        "approved",
        "rejected",
        name="graduation_request_status",
        schema="school",
        create_type=False,
    )
    migration_status = postgresql.ENUM(
        "pending",
        "in_progress",
        "succeeded",
        "failed",
        name="graduation_migration_status",
        schema="school",
        create_type=False,
    )

    op.create_table(
        "graduation_requests",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "student_user_id",
            sa.String(36),
            sa.ForeignKey("school.users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "school_id",
            sa.String(36),
            sa.ForeignKey("school.schools.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("requested_by_user_id", sa.String(36), nullable=False),
        sa.Column("approved_by_user_id", sa.String(36), nullable=True),
        sa.Column("status", request_status, nullable=False, server_default="pending"),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        schema="school",
    )
    op.create_index(
        "ix_graduation_requests_student_user_id",
        "graduation_requests",
        ["student_user_id"],
        schema="school",
    )
    op.create_index(
        "ix_graduation_requests_school_id",
        "graduation_requests",
        ["school_id"],
        schema="school",
    )

    op.create_table(
        "graduation_migration_log",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "student_user_id",
            sa.String(36),
            sa.ForeignKey("school.users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("graduated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("migration_scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("migration_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("migration_status", migration_status, nullable=False, server_default="pending"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("migrated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        schema="school",
    )
    op.create_index(
        "ix_graduation_migration_log_student_user_id",
        "graduation_migration_log",
        ["student_user_id"],
        schema="school",
    )
    op.create_index(
        "ix_graduation_migration_log_status",
        "graduation_migration_log",
        ["migration_status"],
        schema="school",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_graduation_migration_log_status", table_name="graduation_migration_log", schema="school"
    )
    op.drop_index(
        "ix_graduation_migration_log_student_user_id",
        table_name="graduation_migration_log",
        schema="school",
    )
    op.drop_table("graduation_migration_log", schema="school")
    op.drop_index(
        "ix_graduation_requests_school_id", table_name="graduation_requests", schema="school"
    )
    op.drop_index(
        "ix_graduation_requests_student_user_id", table_name="graduation_requests", schema="school"
    )
    op.drop_table("graduation_requests", schema="school")
    op.execute("DROP TYPE IF EXISTS school.graduation_migration_status")
    op.execute("DROP TYPE IF EXISTS school.graduation_request_status")
    op.drop_column("student_profiles", "migration_reminder_sent_days", schema="school")
    op.drop_column("student_profiles", "migrated_at", schema="school")
    op.drop_column("student_profiles", "migrated_out", schema="school")
    op.drop_column("student_profiles", "graduated_at", schema="school")
    op.drop_column("student_profiles", "is_graduated", schema="school")
