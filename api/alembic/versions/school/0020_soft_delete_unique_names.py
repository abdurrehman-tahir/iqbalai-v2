"""Scope district/school name uniqueness to active (non-deleted) rows.

Revision ID: school_0020
Revises: school_0019
Create Date: 2026-06-12

Soft-deleted districts/schools kept the old full-table unique constraints, so
re-creating the same name after delete failed with IntegrityError despite the
service only checking active rows.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "school_0020"
down_revision: str = "school_0019"
branch_labels: tuple[()] = ()
depends_on: str | None = None


def upgrade() -> None:
    op.drop_constraint("districts_name_uq", "districts", schema="school", type_="unique")
    op.create_index(
        "districts_name_uq",
        "districts",
        ["name"],
        unique=True,
        schema="school",
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.drop_constraint("schools_district_name_uq", "schools", schema="school", type_="unique")
    op.create_index(
        "schools_district_name_uq",
        "schools",
        ["district_id", "name"],
        unique=True,
        schema="school",
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("schools_district_name_uq", table_name="schools", schema="school")
    op.create_unique_constraint(
        "schools_district_name_uq",
        "schools",
        ["district_id", "name"],
        schema="school",
    )

    op.drop_index("districts_name_uq", table_name="districts", schema="school")
    op.create_unique_constraint("districts_name_uq", "districts", ["name"], schema="school")
