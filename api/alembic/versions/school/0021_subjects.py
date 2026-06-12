"""Add subjects table (school subject catalogue) to school schema.

Revision ID: school_0021
Revises: school_0020
Create Date: 2026-06-13

T-041 (M-03 Subjects + GSO): create the school-scoped subject catalogue.

Per flow-2 §3.2 a Subject is ``{school_id, name, language}`` plus a ``status``
(active | archived) domain state. The ``(school_id, name)`` unique index is scoped to
active (non-deleted) rows — matching the districts/schools partial-unique pattern
(school_0020) — so a soft-deleted name can be re-created, while an *archived* subject
(still non-deleted) keeps occupying its slot. ``school_id`` FK is ``ON DELETE RESTRICT``
(§4.6). Not RLS-managed beyond the service-layer school scoping (these rows carry
``school_id`` but enforcement is at the repository/role layer for M-03, as with M-02).

Purpose: Create the subjects catalogue table + status enum for M-03.
Risk: low
Reversible: yes
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "school_0021"
down_revision: str = "school_0020"
branch_labels: tuple[()] = ()
depends_on: str | None = None


def upgrade() -> None:
    conn = op.get_bind()
    if conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = 'school' AND table_name = 'subjects'"
        )
    ).scalar():
        return

    # Native enum for the active|archived domain state (§4.9). create_type=False on the
    # ORM column, so the type is owned here.
    op.execute("CREATE TYPE school.subjects_status_enum AS ENUM ('active', 'archived')")

    subject_status = postgresql.ENUM(
        "active", "archived", name="subjects_status_enum", schema="school", create_type=False
    )

    op.create_table(
        "subjects",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "school_id",
            sa.String(36),
            sa.ForeignKey("school.schools.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("language", sa.String(20), nullable=False),
        sa.Column("status", subject_status, nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        schema="school",
    )
    # Name uniqueness scoped to active (non-deleted) rows.
    op.create_index(
        "subjects_school_name_uq",
        "subjects",
        ["school_id", "name"],
        unique=True,
        schema="school",
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index("ix_subjects_school_id", "subjects", ["school_id"], schema="school")
    # deleted_at index from SoftDeleteMixin (§4.4).
    op.create_index("ix_subjects_deleted_at", "subjects", ["deleted_at"], schema="school")


def downgrade() -> None:
    op.drop_index("ix_subjects_deleted_at", table_name="subjects", schema="school")
    op.drop_index("ix_subjects_school_id", table_name="subjects", schema="school")
    op.drop_index("subjects_school_name_uq", table_name="subjects", schema="school")
    op.drop_table("subjects", schema="school")
    op.execute("DROP TYPE IF EXISTS school.subjects_status_enum")
