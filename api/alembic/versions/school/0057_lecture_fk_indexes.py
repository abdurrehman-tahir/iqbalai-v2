"""School migration: FK indexes on lecture_links + lecture_assignments.

Revision ID: school_0057
Revises: school_0056
Create Date: 2026-09-10

Purpose: ARCH §4 requires an index on every foreign key. The T-122/T-123
tables shipped lecture_id indexes but omitted indexes on created_by_user_id,
student_user_id, and section_id. Model columns now declare index=True;
this migration adds the matching DB indexes.
Risk: low — additive indexes only.
Reversible: yes
"""

from __future__ import annotations

from alembic import op

revision: str = "school_0057"
down_revision: str = "school_0056"
branch_labels: tuple[()] = ()
depends_on: str | None = None

_SCHEMA = "school"


def upgrade() -> None:
    op.create_index(
        "ix_school_lecture_links_created_by_user_id",
        "lecture_links",
        ["created_by_user_id"],
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_school_lecture_assignments_student_user_id",
        "lecture_assignments",
        ["student_user_id"],
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_school_lecture_assignments_section_id",
        "lecture_assignments",
        ["section_id"],
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_school_lecture_assignments_created_by_user_id",
        "lecture_assignments",
        ["created_by_user_id"],
        schema=_SCHEMA,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_school_lecture_assignments_created_by_user_id",
        table_name="lecture_assignments",
        schema=_SCHEMA,
    )
    op.drop_index(
        "ix_school_lecture_assignments_section_id",
        table_name="lecture_assignments",
        schema=_SCHEMA,
    )
    op.drop_index(
        "ix_school_lecture_assignments_student_user_id",
        table_name="lecture_assignments",
        schema=_SCHEMA,
    )
    op.drop_index(
        "ix_school_lecture_links_created_by_user_id",
        table_name="lecture_links",
        schema=_SCHEMA,
    )
