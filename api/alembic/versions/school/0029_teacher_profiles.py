"""Create teacher_profiles table — T-053.

Revision ID: school_0029
Revises: school_0028
Create Date: 2026-06-16

Purpose: School teacher onboarding profile + profile_completed_at gate.
Risk: low
Reversible: yes
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "school_0029"
down_revision: str = "school_0028"
branch_labels: tuple[()] = ()
depends_on: str | None = None


def upgrade() -> None:
    conn = op.get_bind()
    if conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = 'school' AND table_name = 'teacher_profiles'"
        )
    ).scalar():
        return

    op.create_table(
        "teacher_profiles",
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("region_province", sa.String(100), nullable=False),
        sa.Column("region_district", sa.String(200), nullable=True),
        sa.Column("bio", sa.Text(), nullable=True),
        sa.Column("language_preference", sa.String(10), nullable=False),
        sa.Column("subject_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("profile_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(now() AT TIME ZONE 'UTC')"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(now() AT TIME ZONE 'UTC')"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["school.users.id"],
            name="teacher_profiles_user_id_fkey",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("user_id"),
        schema="school",
    )
    op.create_index(
        "ix_teacher_profiles_deleted_at",
        "teacher_profiles",
        ["deleted_at"],
        schema="school",
    )


def downgrade() -> None:
    op.drop_index("ix_teacher_profiles_deleted_at", table_name="teacher_profiles", schema="school")
    op.drop_table("teacher_profiles", schema="school")
