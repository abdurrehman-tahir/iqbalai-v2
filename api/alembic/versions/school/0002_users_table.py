"""Add users table to school schema.

Revision ID: school_0002
Revises: school_0001
Create Date: 2026-05-20

"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "school_0002"
down_revision: str = "school_0001"
branch_labels: tuple[()] = ()
depends_on: str | None = None


def upgrade() -> None:
    # Create the userrole enum type
    op.execute(
        "CREATE TYPE school.userrole AS ENUM ("
        "'platform_admin', 'district_admin', 'school_admin', "
        "'coordinator', 'teacher', 'student', 'parent')"
        ")"
    )

    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("authentik_id", sa.String(255), nullable=False, unique=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("school_id", sa.String(36), nullable=True),
        sa.Column("district_id", sa.String(36), nullable=True),
        sa.Column("scoped_ids", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        schema="school",
    )
    op.create_index(
        "ix_users_authentik_id", "users", ["authentik_id"], unique=True, schema="school"
    )
    op.create_index("ix_users_email", "users", ["email"], schema="school")
    op.create_index("ix_users_school_id", "users", ["school_id"], schema="school")
    op.create_index("ix_users_district_id", "users", ["district_id"], schema="school")

    # Enable Row Level Security
    op.execute("ALTER TABLE school.users ENABLE ROW LEVEL SECURITY")

    # RLS policy: users can only see records in their school
    op.execute("""
        CREATE POLICY users_school_isolation ON school.users
        USING (
            school_id = current_setting('app.current_school_id', true)
            OR current_setting('app.current_role', true) = 'platform_admin'
        )
    """)

    # Cross-schema read-only view for platform admin access
    op.execute("""
        CREATE VIEW independent.users_readonly AS
        SELECT id, email, display_name, role, created_at
        FROM school.users
        WHERE deleted_at IS NULL
    """)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS independent.users_readonly")
    op.execute("DROP POLICY IF EXISTS users_school_isolation ON school.users")
    op.drop_index("ix_users_district_id", table_name="users", schema="school")
    op.drop_index("ix_users_school_id", table_name="users", schema="school")
    op.drop_index("ix_users_email", table_name="users", schema="school")
    op.drop_index("ix_users_authentik_id", table_name="users", schema="school")
    op.drop_table("users", schema="school")
    op.execute("DROP TYPE IF EXISTS school.userrole")
