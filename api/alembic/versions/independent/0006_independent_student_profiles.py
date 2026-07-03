"""Add independent student profiles table.

Revision ID: independent_0006
Revises: independent_0005
Create Date: 2026-06-22

Purpose: Independent student onboarding (M-05 T-071).
Risk: low
Reversible: yes
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "independent_0006"
down_revision: str = "independent_0005"
branch_labels: tuple[()] = ()
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "independent_student_profiles",
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("independent.users.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("language_preference", sa.String(10), nullable=False),
        sa.Column("grade_level", sa.Integer(), nullable=False),
        sa.Column("exam_syllabus_id", sa.String(36), nullable=False),
        sa.Column("exam_date", sa.Date(), nullable=True),
        sa.Column("profile_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        schema="independent",
    )
    op.create_index(
        "ix_independent_student_profiles_deleted_at",
        "independent_student_profiles",
        ["deleted_at"],
        schema="independent",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_independent_student_profiles_deleted_at",
        table_name="independent_student_profiles",
        schema="independent",
    )
    op.drop_table("independent_student_profiles", schema="independent")
