"""Add districts and schools tables to school schema.

Revision ID: school_0012
Revises: school_0011
Create Date: 2026-06-12

T-028 (M-02 School Onboarding): create the org-hierarchy root tables.

Per ARCH §3.3 `districts` and `schools` are NOT tenant-scoped — they *are* the
tenants. Access is admin-only and controlled by role, so (unlike `school.users`)
these tables deliberately carry **no RLS policy**. District-Admin scoping is
enforced at the repository/role layer in T-029, not at the DB level.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "school_0012"
down_revision: str = "school_0011"
branch_labels: tuple[()] = ()
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "districts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("name", name="districts_name_uq"),
        schema="school",
    )

    op.create_table(
        "schools",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "district_id",
            sa.String(36),
            sa.ForeignKey("school.districts.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("district_id", "name", name="schools_district_name_uq"),
        schema="school",
    )
    op.create_index("ix_schools_district_id", "schools", ["district_id"], schema="school")

    # NOTE: no `ENABLE ROW LEVEL SECURITY` here — per ARCH §3.3 these are the
    # tenant-root tables (not tenant-scoped). RLS lives on tenant-scoped tables only.

    # Seed data (acceptance #3): one sample district + one sample school under it.
    op.execute(
        """
        INSERT INTO school.districts (id, name, created_at, updated_at)
        VALUES (
            '00000000-0000-0000-0000-0000000d1571',
            'Sample District',
            now(),
            now()
        )
        """
    )
    op.execute(
        """
        INSERT INTO school.schools (id, district_id, name, created_at, updated_at)
        VALUES (
            '00000000-0000-0000-0000-00000005c001',
            '00000000-0000-0000-0000-0000000d1571',
            'Sample School',
            now(),
            now()
        )
        """
    )


def downgrade() -> None:
    op.drop_index("ix_schools_district_id", table_name="schools", schema="school")
    op.drop_table("schools", schema="school")
    op.drop_table("districts", schema="school")
