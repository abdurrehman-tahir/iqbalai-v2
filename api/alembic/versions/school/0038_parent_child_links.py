"""Add parent_child_links table for opt-in parent linking.

Revision ID: school_0038
Revises: school_0037
Create Date: 2026-06-22

T-081 (M-06): parent initiates link → student approves (§6.13).

Purpose: parent_child_links table with pending/approved/revoked status.
Risk: low
Reversible: yes
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "school_0038"
down_revision: str = "school_0037"
branch_labels: tuple[()] = ()
depends_on: str | None = None


def upgrade() -> None:
    conn = op.get_bind()
    if conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = 'school' AND table_name = 'parent_child_links'"
        )
    ).scalar():
        return

    op.execute(
        "CREATE TYPE school.parent_child_link_status AS ENUM ('pending', 'approved', 'revoked')"
    )

    link_status = postgresql.ENUM(
        "pending",
        "approved",
        "revoked",
        name="parent_child_link_status",
        schema="school",
        create_type=False,
    )

    op.create_table(
        "parent_child_links",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "parent_user_id",
            sa.String(36),
            sa.ForeignKey("school.users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "student_user_id",
            sa.String(36),
            sa.ForeignKey("school.users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("status", link_status, nullable=False, server_default="pending"),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejected_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "parent_user_id",
            "student_user_id",
            name="uq_parent_child_links_parent_student",
        ),
        schema="school",
    )
    op.create_index(
        "ix_parent_child_links_parent_user_id",
        "parent_child_links",
        ["parent_user_id"],
        schema="school",
    )
    op.create_index(
        "ix_parent_child_links_student_user_id",
        "parent_child_links",
        ["student_user_id"],
        schema="school",
    )
    op.create_index(
        "ix_parent_child_links_status",
        "parent_child_links",
        ["status"],
        schema="school",
    )


def downgrade() -> None:
    op.drop_index("ix_parent_child_links_status", table_name="parent_child_links", schema="school")
    op.drop_index(
        "ix_parent_child_links_student_user_id", table_name="parent_child_links", schema="school"
    )
    op.drop_index(
        "ix_parent_child_links_parent_user_id", table_name="parent_child_links", schema="school"
    )
    op.drop_table("parent_child_links", schema="school")
    op.execute("DROP TYPE IF EXISTS school.parent_child_link_status")
