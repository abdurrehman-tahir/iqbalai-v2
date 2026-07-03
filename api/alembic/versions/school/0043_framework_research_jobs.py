"""Framework research jobs — Pattern-A AI research run records.

Revision ID: school_0043
Revises: school_0042
Create Date: 2026-07-02

T-093 (M-07): one row per AI research run for an exam framework (ARCH §8.21).
Platform-tier, school schema (frameworks are platform-shared). Records terminal
status, estimated USD spend, cited-source count, error, and the produced plan.

Purpose: framework_research_jobs table + framework_research_job_status enum.
Risk: low
Reversible: yes
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "school_0043"
down_revision: str = "school_0042"
branch_labels: tuple[()] = ()
depends_on: str | None = None


def upgrade() -> None:
    conn = op.get_bind()
    if conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = 'school' AND table_name = 'framework_research_jobs'"
        )
    ).scalar():
        return

    op.execute(
        "CREATE TYPE school.framework_research_job_status AS ENUM ("
        "'running', 'succeeded', 'partial', 'research_failed'"
        ")"
    )

    job_status = postgresql.ENUM(
        "running",
        "succeeded",
        "partial",
        "research_failed",
        name="framework_research_job_status",
        schema="school",
        create_type=False,
    )

    op.create_table(
        "framework_research_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "framework_id",
            sa.String(36),
            sa.ForeignKey("school.exam_frameworks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", job_status, nullable=False, server_default="running"),
        sa.Column("cost_usd", sa.Numeric(10, 4), nullable=False, server_default="0"),
        sa.Column("sources_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "study_plan_id",
            sa.String(36),
            sa.ForeignKey("school.framework_study_plans.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("cost_usd >= 0", name="framework_research_jobs_cost_nonneg_check"),
        sa.CheckConstraint(
            "sources_count >= 0", name="framework_research_jobs_sources_nonneg_check"
        ),
        schema="school",
    )
    op.create_index(
        "ix_framework_research_jobs_framework_id",
        "framework_research_jobs",
        ["framework_id"],
        schema="school",
    )
    op.create_index(
        "ix_framework_research_jobs_study_plan_id",
        "framework_research_jobs",
        ["study_plan_id"],
        schema="school",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_framework_research_jobs_study_plan_id",
        table_name="framework_research_jobs",
        schema="school",
    )
    op.drop_index(
        "ix_framework_research_jobs_framework_id",
        table_name="framework_research_jobs",
        schema="school",
    )
    op.drop_table("framework_research_jobs", schema="school")
    op.execute("DROP TYPE IF EXISTS school.framework_research_job_status")
