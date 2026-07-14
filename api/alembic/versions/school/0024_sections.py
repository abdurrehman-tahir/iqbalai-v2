"""Add sections table to school schema.

Revision ID: school_0024
Revises: school_0023
Create Date: 2026-06-15

T-044 (M-03): optional sections under grades with default-internal auto-creation.

Purpose: Section model for enrollment targets.
Risk: low
Reversible: yes
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "school_0024"
down_revision: str = "school_0023"
branch_labels: tuple[()] = ()
depends_on: str | None = None


def upgrade() -> None:
    conn = op.get_bind()
    if conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = 'school' AND table_name = 'sections'"
        )
    ).scalar():
        return

    op.execute("CREATE TYPE school.sections_status_enum AS ENUM ('active', 'archived')")

    section_status = postgresql.ENUM(
        "active", "archived", name="sections_status_enum", schema="school", create_type=False
    )

    op.create_table(
        "sections",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "grade_id",
            sa.String(36),
            sa.ForeignKey("school.grades.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("is_default_internal", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("status", section_status, nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        schema="school",
    )
    op.create_index(
        "sections_grade_name_uq",
        "sections",
        ["grade_id", "name"],
        unique=True,
        schema="school",
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index("ix_sections_grade_id", "sections", ["grade_id"], schema="school")
    op.create_index("ix_sections_deleted_at", "sections", ["deleted_at"], schema="school")


def downgrade() -> None:
    op.drop_index("ix_sections_deleted_at", table_name="sections", schema="school")
    op.drop_index("ix_sections_grade_id", table_name="sections", schema="school")
    op.drop_index("sections_grade_name_uq", table_name="sections", schema="school")
    op.drop_table("sections", schema="school")
    op.execute("DROP TYPE IF EXISTS school.sections_status_enum")
