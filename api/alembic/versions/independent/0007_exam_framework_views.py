"""Cross-schema read-only views for exam frameworks + study plans (T-091).

Revision ID: independent_0007
Revises: independent_0006
Create Date: 2026-07-02

Exposes school.exam_frameworks (published only) and school.framework_study_plans
(approved only) to the independent schema read-only (ARCH §3.16 / §4.21). Cross-
schema foreign keys are forbidden — views are the only allowed reference.

Purpose: independent.exam_frameworks + independent.framework_study_plans views.
Risk: low
Reversible: yes
"""

from __future__ import annotations

from alembic import op

revision: str = "independent_0007"
down_revision: str = "independent_0006"
branch_labels: tuple[()] = ()
depends_on: tuple[str, ...] | None = ("school_0042",)


def upgrade() -> None:
    op.execute("""
        CREATE VIEW independent.exam_frameworks AS
        SELECT
            id,
            name,
            exam_target,
            region,
            target_grade_range,
            language,
            status,
            created_by,
            created_at,
            updated_at,
            deleted_at
        FROM school.exam_frameworks
        WHERE status = 'published' AND deleted_at IS NULL
    """)
    op.execute("""
        CREATE VIEW independent.framework_study_plans AS
        SELECT
            id,
            framework_id,
            version,
            content_jsonb,
            sources_cited_jsonb,
            generated_at,
            approved_by,
            approved_at,
            status,
            created_at,
            updated_at
        FROM school.framework_study_plans
        WHERE status = 'approved'
    """)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS independent.framework_study_plans")
    op.execute("DROP VIEW IF EXISTS independent.exam_frameworks")
