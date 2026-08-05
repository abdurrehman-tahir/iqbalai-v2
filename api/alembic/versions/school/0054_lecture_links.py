"""School migration: lecture_links table (T-122, #21).

Revision ID: school_0054
Revises: school_0053
Create Date: 2026-08-05

Purpose: lecture_links (school) — links a lecture into an additional
Grade-Subject offering (self-link, cross-grade/subject linking, flow-5 §3.13).
Risk: low — additive table only.
Reversible: yes
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "school_0054"
down_revision: str = "school_0053"
branch_labels: tuple[()] = ()
depends_on: str | None = None

_SCHEMA = "school"


def upgrade() -> None:
    op.create_table(
        "lecture_links",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "lecture_id",
            sa.String(36),
            sa.ForeignKey(f"{_SCHEMA}.lectures.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "target_grade_subject_offering_id",
            sa.String(36),
            sa.ForeignKey(f"{_SCHEMA}.grade_subject_offerings.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "created_by_user_id",
            sa.String(36),
            sa.ForeignKey(f"{_SCHEMA}.users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "lecture_id",
            "target_grade_subject_offering_id",
            name="lecture_links_lecture_target_uq",
        ),
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_lecture_links_lecture_id",
        "lecture_links",
        ["lecture_id"],
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_lecture_links_target_grade_subject_offering_id",
        "lecture_links",
        ["target_grade_subject_offering_id"],
        schema=_SCHEMA,
    )


def downgrade() -> None:
    op.drop_table("lecture_links", schema=_SCHEMA)
