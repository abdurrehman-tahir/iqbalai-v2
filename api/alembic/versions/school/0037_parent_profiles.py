"""Add parent profiles for public parent signup.

Revision ID: school_0037
Revises: school_0036
Create Date: 2026-06-22

T-080 (M-06): parent_profiles table for PARENT_ACTIVE_UNLINKED lifecycle.

Purpose: parent_profiles table for parent registration and unlinked tracking.
Risk: low
Reversible: yes
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "school_0037"
down_revision: str = "school_0036"
branch_labels: tuple[()] = ()
depends_on: str | None = None


def upgrade() -> None:
    conn = op.get_bind()
    if conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = 'school' AND table_name = 'parent_profiles'"
        )
    ).scalar():
        return

    op.create_table(
        "parent_profiles",
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("school.users.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("language_preference", sa.String(10), nullable=False),
        sa.Column("is_email_verified", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("unlinked_since", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        schema="school",
    )
    op.create_index(
        "ix_parent_profiles_deleted_at",
        "parent_profiles",
        ["deleted_at"],
        schema="school",
    )
    op.create_index(
        "ix_parent_profiles_unlinked_since",
        "parent_profiles",
        ["unlinked_since"],
        schema="school",
    )


def downgrade() -> None:
    op.drop_index("ix_parent_profiles_unlinked_since", table_name="parent_profiles", schema="school")
    op.drop_index("ix_parent_profiles_deleted_at", table_name="parent_profiles", schema="school")
    op.drop_table("parent_profiles", schema="school")
