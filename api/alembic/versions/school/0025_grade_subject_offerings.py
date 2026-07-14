"""Add grade_subject_offerings table to school schema.

Revision ID: school_0025
Revises: school_0024
Create Date: 2026-06-15

T-045 (M-03): GradeSubjectOffering — offer subjects to grades.

Purpose: Links subject catalogue entries to grades per academic session.
Risk: low
Reversible: yes
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "school_0025"
down_revision: str = "school_0024"
branch_labels: tuple[()] = ()
depends_on: str | None = None


def upgrade() -> None:
    conn = op.get_bind()
    if conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = 'school' AND table_name = 'grade_subject_offerings'"
        )
    ).scalar():
        return

    op.execute(
        "CREATE TYPE school.grade_subject_offerings_status_enum AS ENUM ('active', 'archived')"
    )

    offering_status = postgresql.ENUM(
        "active",
        "archived",
        name="grade_subject_offerings_status_enum",
        schema="school",
        create_type=False,
    )

    op.create_table(
        "grade_subject_offerings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "school_id",
            sa.String(36),
            sa.ForeignKey("school.schools.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "grade_id",
            sa.String(36),
            sa.ForeignKey("school.grades.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "subject_id",
            sa.String(36),
            sa.ForeignKey("school.subjects.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "assigned_teacher_id",
            sa.String(36),
            sa.ForeignKey("school.users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("academic_session", sa.String(50), nullable=False),
        sa.Column("status", offering_status, nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        schema="school",
    )
    op.create_index(
        "grade_subject_offerings_grade_subject_uq",
        "grade_subject_offerings",
        ["grade_id", "subject_id"],
        unique=True,
        schema="school",
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_grade_subject_offerings_school_id",
        "grade_subject_offerings",
        ["school_id"],
        schema="school",
    )
    op.create_index(
        "ix_grade_subject_offerings_grade_id",
        "grade_subject_offerings",
        ["grade_id"],
        schema="school",
    )
    op.create_index(
        "ix_grade_subject_offerings_subject_id",
        "grade_subject_offerings",
        ["subject_id"],
        schema="school",
    )
    op.create_index(
        "ix_grade_subject_offerings_assigned_teacher_id",
        "grade_subject_offerings",
        ["assigned_teacher_id"],
        schema="school",
    )
    op.create_index(
        "ix_grade_subject_offerings_deleted_at",
        "grade_subject_offerings",
        ["deleted_at"],
        schema="school",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_grade_subject_offerings_deleted_at",
        table_name="grade_subject_offerings",
        schema="school",
    )
    op.drop_index(
        "ix_grade_subject_offerings_assigned_teacher_id",
        table_name="grade_subject_offerings",
        schema="school",
    )
    op.drop_index(
        "ix_grade_subject_offerings_subject_id",
        table_name="grade_subject_offerings",
        schema="school",
    )
    op.drop_index(
        "ix_grade_subject_offerings_grade_id",
        table_name="grade_subject_offerings",
        schema="school",
    )
    op.drop_index(
        "ix_grade_subject_offerings_school_id",
        table_name="grade_subject_offerings",
        schema="school",
    )
    op.drop_index(
        "grade_subject_offerings_grade_subject_uq",
        table_name="grade_subject_offerings",
        schema="school",
    )
    op.drop_table("grade_subject_offerings", schema="school")
    op.execute("DROP TYPE IF EXISTS school.grade_subject_offerings_status_enum")
