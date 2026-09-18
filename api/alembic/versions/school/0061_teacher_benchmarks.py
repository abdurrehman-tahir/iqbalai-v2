"""School migration: teacher_benchmarks table (T-129, Flow 5 §3.11 #37).

Revision ID: school_0061
Revises: school_0060
Create Date: 2026-09-11

Purpose: anonymized weekly percentile standing within a (subject, grade_range,
region) cohort (T-139). School schema only — N/A for independent teachers
(no peer cohort in a one-person tenant).
Risk: low — additive table only.
Reversible: yes
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "school_0061"
down_revision: str = "school_0060"
branch_labels: tuple[()] = ()
depends_on: str | None = None

_SCHEMA = "school"


def upgrade() -> None:
    op.create_table(
        "teacher_benchmarks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "teacher_user_id",
            sa.String(36),
            sa.ForeignKey(f"{_SCHEMA}.users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "subject_id",
            sa.String(36),
            sa.ForeignKey(f"{_SCHEMA}.subjects.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("grade_range", sa.String(50), nullable=False),
        sa.Column("region", sa.String(100), nullable=False),
        sa.Column("percentile", sa.Integer(), nullable=True),
        sa.Column("cohort_size", sa.Integer(), nullable=True),
        sa.Column("opted_out", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "percentile IS NULL OR (percentile >= 0 AND percentile <= 100)",
            name="teacher_benchmarks_percentile_range_check",
        ),
        sa.CheckConstraint(
            "cohort_size IS NULL OR cohort_size >= 0",
            name="teacher_benchmarks_cohort_size_nonneg_check",
        ),
        sa.UniqueConstraint(
            "teacher_user_id",
            "subject_id",
            "grade_range",
            "region",
            name="teacher_benchmarks_teacher_cohort_uq",
        ),
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_teacher_benchmarks_teacher_user_id",
        "teacher_benchmarks",
        ["teacher_user_id"],
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_teacher_benchmarks_cohort",
        "teacher_benchmarks",
        ["subject_id", "grade_range", "region"],
        schema=_SCHEMA,
    )


def downgrade() -> None:
    op.drop_table("teacher_benchmarks", schema=_SCHEMA)
