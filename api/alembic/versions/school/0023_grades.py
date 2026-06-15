"""Add grades table to school schema.

Revision ID: school_0023
Revises: school_0022
Create Date: 2026-06-15

T-043 (M-03): session-scoped grade entities with level_ordinal for cross-grade rules.

Purpose: Grade model for academic structure.
Risk: low
Reversible: yes
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = "school_0023"
down_revision: str = "school_0022"
branch_labels: tuple[()] = ()
depends_on: str | None = None


def upgrade() -> None:
    conn = op.get_bind()
    if conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = 'school' AND table_name = 'grades'"
        )
    ).scalar():
        return

    op.execute("CREATE TYPE school.grades_status_enum AS ENUM ('active', 'archived')")

    grade_status = postgresql.ENUM(
        "active", "archived", name="grades_status_enum", schema="school", create_type=False
    )

    op.create_table(
        "grades",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "school_id",
            sa.String(36),
            sa.ForeignKey("school.schools.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("academic_session", sa.String(50), nullable=False),
        sa.Column("level_ordinal", sa.Integer(), nullable=False),
        sa.Column(
            "promoted_from_grade_id",
            sa.String(36),
            sa.ForeignKey("school.grades.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("status", grade_status, nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        schema="school",
    )
    op.create_index(
        "grades_school_name_session_uq",
        "grades",
        ["school_id", "name", "academic_session"],
        unique=True,
        schema="school",
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index("ix_grades_school_id", "grades", ["school_id"], schema="school")
    op.create_index("ix_grades_academic_session", "grades", ["academic_session"], schema="school")
    op.create_index("ix_grades_deleted_at", "grades", ["deleted_at"], schema="school")


def downgrade() -> None:
    op.drop_index("ix_grades_deleted_at", table_name="grades", schema="school")
    op.drop_index("ix_grades_academic_session", table_name="grades", schema="school")
    op.drop_index("ix_grades_school_id", table_name="grades", schema="school")
    op.drop_index("grades_school_name_session_uq", table_name="grades", schema="school")
    op.drop_table("grades", schema="school")
    op.execute("DROP TYPE IF EXISTS school.grades_status_enum")
