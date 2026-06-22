"""Add school student profiles for onboarding.

Revision ID: school_0035
Revises: school_0034
Create Date: 2026-06-22

T-078 (M-06): PROFILE_BASIC + mode selection through READY_TO_STUDY.

Purpose: student_profiles table for school student onboarding state.
Risk: low
Reversible: yes
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "school_0035"
down_revision: str = "school_0034"
branch_labels: tuple[()] = ()
depends_on: str | None = None


def upgrade() -> None:
    conn = op.get_bind()
    if conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = 'school' AND table_name = 'student_profiles'"
        )
    ).scalar():
        return

    op.create_table(
        "student_profiles",
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("school.users.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("language_preference", sa.String(10), nullable=False),
        sa.Column("tos_accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("profile_basic_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lecture_mode_enabled", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("self_study_mode_enabled", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("deferrable_banner_dismissed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        schema="school",
    )
    op.create_index(
        "ix_student_profiles_deleted_at",
        "student_profiles",
        ["deleted_at"],
        schema="school",
    )


def downgrade() -> None:
    op.drop_index("ix_student_profiles_deleted_at", table_name="student_profiles", schema="school")
    op.drop_table("student_profiles", schema="school")
