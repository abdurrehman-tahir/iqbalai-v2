"""Add student enrollments table and invited user status.

Revision ID: school_0034
Revises: school_0033
Create Date: 2026-06-22

T-077 (M-06): Coordinator enrollment into Grade+Section; school students start INVITED.

Purpose: student_enrollments table + useraccountstatus.invited enum value.
Risk: low
Reversible: yes
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "school_0034"
down_revision: str = "school_0033"
branch_labels: tuple[()] = ()
depends_on: str | None = None


def upgrade() -> None:
    conn = op.get_bind()
    op.execute("ALTER TYPE school.useraccountstatus ADD VALUE IF NOT EXISTS 'invited'")

    if conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = 'school' AND table_name = 'student_enrollments'"
        )
    ).scalar():
        return

    op.execute(
        "CREATE TYPE school.student_enrollment_status AS ENUM ('active', 'withdrawn', 'graduated')"
    )

    enrollment_status = postgresql.ENUM(
        "active",
        "withdrawn",
        "graduated",
        name="student_enrollment_status",
        schema="school",
        create_type=False,
    )

    op.create_table(
        "student_enrollments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "school_id",
            sa.String(36),
            sa.ForeignKey("school.schools.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "student_user_id",
            sa.String(36),
            sa.ForeignKey("school.users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "grade_id",
            sa.String(36),
            sa.ForeignKey("school.grades.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "section_id",
            sa.String(36),
            sa.ForeignKey("school.sections.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("academic_session", sa.String(50), nullable=False),
        sa.Column("status", enrollment_status, nullable=False, server_default="active"),
        sa.Column("enrolled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        schema="school",
    )
    op.create_index(
        "ix_student_enrollments_school_id",
        "student_enrollments",
        ["school_id"],
        schema="school",
    )
    op.create_index(
        "ix_student_enrollments_student_user_id",
        "student_enrollments",
        ["student_user_id"],
        schema="school",
    )
    op.create_index(
        "ix_student_enrollments_grade_id",
        "student_enrollments",
        ["grade_id"],
        schema="school",
    )
    op.create_index(
        "ix_student_enrollments_section_id",
        "student_enrollments",
        ["section_id"],
        schema="school",
    )
    op.create_index(
        "ix_student_enrollments_deleted_at",
        "student_enrollments",
        ["deleted_at"],
        schema="school",
    )
    op.create_index(
        "student_enrollments_active_session_uq",
        "student_enrollments",
        ["student_user_id", "academic_session"],
        unique=True,
        schema="school",
        postgresql_where=sa.text(
            "deleted_at IS NULL AND status = 'active'"
        ),
    )


def downgrade() -> None:
    op.drop_index(
        "student_enrollments_active_session_uq",
        table_name="student_enrollments",
        schema="school",
    )
    op.drop_index("ix_student_enrollments_deleted_at", table_name="student_enrollments", schema="school")
    op.drop_index("ix_student_enrollments_section_id", table_name="student_enrollments", schema="school")
    op.drop_index("ix_student_enrollments_grade_id", table_name="student_enrollments", schema="school")
    op.drop_index("ix_student_enrollments_student_user_id", table_name="student_enrollments", schema="school")
    op.drop_index("ix_student_enrollments_school_id", table_name="student_enrollments", schema="school")
    op.drop_table("student_enrollments", schema="school")
    op.execute("DROP TYPE IF EXISTS school.student_enrollment_status")
