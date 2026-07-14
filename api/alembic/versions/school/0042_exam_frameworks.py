"""Exam Framework engine — definitions, versioned study plans, student selections.

Revision ID: school_0042
Revises: school_0041
Create Date: 2026-07-02

T-091 (M-07): platform-shared exam-framework tables (Flow 4 §3.5, ARCH §3.19).
Live in the school schema; exposed read-only to independent via cross-schema views
(independent_0007, ARCH §4.21).

Purpose: exam_frameworks, framework_study_plans, student_framework_selections + enums.
Risk: low
Reversible: yes
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "school_0042"
down_revision: str = "school_0041"
branch_labels: tuple[()] = ()
depends_on: str | None = None


def upgrade() -> None:
    conn = op.get_bind()
    if conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = 'school' AND table_name = 'exam_frameworks'"
        )
    ).scalar():
        return

    op.execute(
        "CREATE TYPE school.exam_framework_status AS ENUM ("
        "'draft', 'researching', 'pending_approval', 'published', 'refreshing', 'deprecated'"
        ")"
    )
    op.execute(
        "CREATE TYPE school.framework_study_plan_status AS ENUM ("
        "'draft', 'pending_approval', 'approved', 'superseded'"
        ")"
    )
    op.execute(
        "CREATE TYPE school.student_framework_selection_tenant_type AS ENUM ("
        "'school', 'independent'"
        ")"
    )
    op.execute(
        "CREATE TYPE school.student_framework_selection_status AS ENUM ('active', 'abandoned')"
    )

    framework_status = postgresql.ENUM(
        "draft",
        "researching",
        "pending_approval",
        "published",
        "refreshing",
        "deprecated",
        name="exam_framework_status",
        schema="school",
        create_type=False,
    )
    plan_status = postgresql.ENUM(
        "draft",
        "pending_approval",
        "approved",
        "superseded",
        name="framework_study_plan_status",
        schema="school",
        create_type=False,
    )
    selection_tenant_type = postgresql.ENUM(
        "school",
        "independent",
        name="student_framework_selection_tenant_type",
        schema="school",
        create_type=False,
    )
    selection_status = postgresql.ENUM(
        "active",
        "abandoned",
        name="student_framework_selection_status",
        schema="school",
        create_type=False,
    )

    # --- exam_frameworks (thin Platform-Admin metadata record) -----------------
    op.create_table(
        "exam_frameworks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("exam_target", sa.String(255), nullable=False),
        sa.Column("region", sa.String(100), nullable=False),
        sa.Column("target_grade_range", postgresql.ARRAY(sa.Integer()), nullable=False),
        sa.Column("language", sa.String(10), nullable=False, server_default="en"),
        sa.Column("status", framework_status, nullable=False, server_default="draft"),
        sa.Column("created_by", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        schema="school",
    )
    op.create_index(
        "ix_exam_frameworks_deleted_at", "exam_frameworks", ["deleted_at"], schema="school"
    )

    # --- framework_study_plans (append-only versioned AI plans) ----------------
    op.create_table(
        "framework_study_plans",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "framework_id",
            sa.String(36),
            sa.ForeignKey("school.exam_frameworks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("content_jsonb", postgresql.JSONB(), nullable=False),
        sa.Column("sources_cited_jsonb", postgresql.JSONB(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("approved_by", sa.String(36), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", plan_status, nullable=False, server_default="draft"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "framework_id", "version", name="framework_study_plans_framework_version_uq"
        ),
        schema="school",
    )
    op.create_index(
        "ix_framework_study_plans_framework_id",
        "framework_study_plans",
        ["framework_id"],
        schema="school",
    )

    # --- student_framework_selections (both tenant types; multi-active allowed) -
    op.create_table(
        "student_framework_selections",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_type", selection_tenant_type, nullable=False),
        sa.Column("student_user_id", sa.String(36), nullable=False),
        sa.Column(
            "framework_id",
            sa.String(36),
            sa.ForeignKey("school.exam_frameworks.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("pinned_version", sa.Integer(), nullable=False),
        sa.Column("status", selection_status, nullable=False, server_default="active"),
        sa.Column("selected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        schema="school",
    )
    # No unique-per-student constraint: a student may hold multiple active selections
    # (Flow 4 §3.5.3, T-091 Acceptance #5).
    op.create_index(
        "ix_student_framework_selections_student_user_id",
        "student_framework_selections",
        ["student_user_id"],
        schema="school",
    )
    op.create_index(
        "ix_student_framework_selections_framework_id",
        "student_framework_selections",
        ["framework_id"],
        schema="school",
    )
    op.create_index(
        "ix_student_framework_selections_deleted_at",
        "student_framework_selections",
        ["deleted_at"],
        schema="school",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_student_framework_selections_deleted_at",
        table_name="student_framework_selections",
        schema="school",
    )
    op.drop_index(
        "ix_student_framework_selections_framework_id",
        table_name="student_framework_selections",
        schema="school",
    )
    op.drop_index(
        "ix_student_framework_selections_student_user_id",
        table_name="student_framework_selections",
        schema="school",
    )
    op.drop_table("student_framework_selections", schema="school")
    op.drop_index(
        "ix_framework_study_plans_framework_id",
        table_name="framework_study_plans",
        schema="school",
    )
    op.drop_table("framework_study_plans", schema="school")
    op.drop_index("ix_exam_frameworks_deleted_at", table_name="exam_frameworks", schema="school")
    op.drop_table("exam_frameworks", schema="school")
    op.execute("DROP TYPE IF EXISTS school.student_framework_selection_status")
    op.execute("DROP TYPE IF EXISTS school.student_framework_selection_tenant_type")
    op.execute("DROP TYPE IF EXISTS school.framework_study_plan_status")
    op.execute("DROP TYPE IF EXISTS school.exam_framework_status")
