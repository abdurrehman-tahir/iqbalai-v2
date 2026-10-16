"""School migration: self-study tables (T-209, Flow 8 §3.1 / §10).

Revision ID: school_0081
Revises: school_0080
Create Date: 2026-10-15

Purpose: student_materials, student_goals, prep_book_topics, study_plans,
study_plan_items, study_plan_days, reminder_preferences in the school schema.
Privacy #72 reuses user_settings.teacher_activity_share (no new table).
Subscription gate hook: study_plans.subscription_tier_id (limits unset).
Risk: low — additive tables + enums.
Reversible: yes

Hand-authored to match self_study.models (model-first; autogenerate pruned).
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "school_0081"
down_revision: str = "school_0080"
branch_labels: tuple[()] = ()
depends_on: str | None = None

_SCHEMA = "school"


def _create_enum_if_missing(qualified_name: str, values_sql: str) -> None:
    op.execute(
        f"""
        DO $$ BEGIN
            CREATE TYPE {qualified_name} AS ENUM ({values_sql});
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$;
        """
    )


def _enum(name: str, *values: str) -> postgresql.ENUM:
    return postgresql.ENUM(
        *values,
        name=name,
        schema=_SCHEMA,
        create_type=False,
    )


def _audit_cols() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(now() AT TIME ZONE 'UTC')"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(now() AT TIME ZONE 'UTC')"),
            nullable=False,
        ),
    ]


def _soft_delete_col() -> sa.Column:
    return sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True)


def upgrade() -> None:
    _create_enum_if_missing(f"{_SCHEMA}.self_study_tenant_type_enum", "'school', 'independent'")
    _create_enum_if_missing(
        f"{_SCHEMA}.student_materials_source_type_enum",
        "'pdf', 'camera', 'gallery', 'typed'",
    )
    _create_enum_if_missing(
        f"{_SCHEMA}.student_materials_book_type_enum",
        "'prep_questions', 'reference_content'",
    )
    _create_enum_if_missing(f"{_SCHEMA}.study_plans_status_enum", "'active', 'archived'")
    _create_enum_if_missing(
        f"{_SCHEMA}.study_plans_granularity_current_enum", "'day', '3day', 'week'"
    )
    _create_enum_if_missing(f"{_SCHEMA}.study_plan_items_granularity_enum", "'day', '3day', 'week'")

    tenant = _enum("self_study_tenant_type_enum", "school", "independent")
    source = _enum("student_materials_source_type_enum", "pdf", "camera", "gallery", "typed")
    book = _enum("student_materials_book_type_enum", "prep_questions", "reference_content")
    status = _enum("study_plans_status_enum", "active", "archived")
    gran_plan = _enum("study_plans_granularity_current_enum", "day", "3day", "week")
    gran_item = _enum("study_plan_items_granularity_enum", "day", "3day", "week")

    op.create_table(
        "student_materials",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("tenant_type", tenant, nullable=False),
        sa.Column("student_user_id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("source_type", source, nullable=False),
        sa.Column("book_type", book, nullable=True),
        sa.Column("storage_key", sa.String(length=1024), nullable=True),
        sa.Column("ocr_text", sa.Text(), nullable=True),
        sa.Column("file_hash", sa.String(length=128), nullable=True),
        sa.Column(
            "added_to_library",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        *_audit_cols(),
        _soft_delete_col(),
        sa.ForeignKeyConstraint(["student_user_id"], [f"{_SCHEMA}.users.id"], ondelete="CASCADE"),
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_student_materials_student_user_id",
        "student_materials",
        ["student_user_id"],
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_student_materials_deleted_at",
        "student_materials",
        ["deleted_at"],
        schema=_SCHEMA,
    )

    op.create_table(
        "student_goals",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("tenant_type", tenant, nullable=False),
        sa.Column("student_user_id", sa.String(length=36), nullable=False),
        sa.Column("goal_date", sa.Date(), nullable=False),
        sa.Column("goal_text", sa.Text(), nullable=False),
        sa.Column("achieved", sa.Boolean(), nullable=True),
        sa.Column("achieved_response_at", sa.DateTime(timezone=True), nullable=True),
        *_audit_cols(),
        sa.ForeignKeyConstraint(["student_user_id"], [f"{_SCHEMA}.users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("student_user_id", "goal_date", name="student_goals_student_date_uq"),
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_student_goals_student_user_id",
        "student_goals",
        ["student_user_id"],
        schema=_SCHEMA,
    )

    op.create_table(
        "prep_book_topics",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("tenant_type", tenant, nullable=False),
        sa.Column("student_material_id", sa.String(length=36), nullable=False),
        sa.Column("topic_label", sa.String(length=500), nullable=False),
        sa.Column("curriculum_topic_id", sa.String(length=36), nullable=True),
        sa.Column("question_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("weight", sa.Float(), nullable=False, server_default="0"),
        sa.Column("extracted_at", sa.DateTime(timezone=True), nullable=False),
        *_audit_cols(),
        sa.ForeignKeyConstraint(
            ["student_material_id"],
            [f"{_SCHEMA}.student_materials.id"],
            ondelete="CASCADE",
        ),
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_prep_book_topics_student_material_id",
        "prep_book_topics",
        ["student_material_id"],
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_prep_book_topics_curriculum_topic_id",
        "prep_book_topics",
        ["curriculum_topic_id"],
        schema=_SCHEMA,
    )

    op.create_table(
        "study_plans",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("tenant_type", tenant, nullable=False),
        sa.Column("student_user_id", sa.String(length=36), nullable=False),
        sa.Column("exam_type_id", sa.String(length=36), nullable=True),
        sa.Column("exam_date", sa.Date(), nullable=True),
        sa.Column("daily_hours", sa.Integer(), nullable=False, server_default="2"),
        sa.Column(
            "strong_topics",
            postgresql.ARRAY(sa.String()),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column("status", status, nullable=False, server_default="active"),
        sa.Column("granularity_current", gran_plan, nullable=False, server_default="day"),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("subscription_tier_id", sa.String(length=36), nullable=True),
        *_audit_cols(),
        _soft_delete_col(),
        sa.ForeignKeyConstraint(["student_user_id"], [f"{_SCHEMA}.users.id"], ondelete="CASCADE"),
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_study_plans_student_user_id",
        "study_plans",
        ["student_user_id"],
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_study_plans_exam_type_id",
        "study_plans",
        ["exam_type_id"],
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_study_plans_subscription_tier_id",
        "study_plans",
        ["subscription_tier_id"],
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_study_plans_deleted_at",
        "study_plans",
        ["deleted_at"],
        schema=_SCHEMA,
    )

    op.create_table(
        "study_plan_items",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("study_plan_id", sa.String(length=36), nullable=False),
        sa.Column("granularity", gran_item, nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column(
            "tasks_jsonb",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("est_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("subject_color", sa.String(length=32), nullable=False, server_default=""),
        *_audit_cols(),
        sa.ForeignKeyConstraint(
            ["study_plan_id"], [f"{_SCHEMA}.study_plans.id"], ondelete="CASCADE"
        ),
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_study_plan_items_study_plan_id",
        "study_plan_items",
        ["study_plan_id"],
        schema=_SCHEMA,
    )

    op.create_table(
        "study_plan_days",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("study_plan_id", sa.String(length=36), nullable=False),
        sa.Column("day_date", sa.Date(), nullable=False),
        sa.Column(
            "scheduled_tasks_jsonb",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "completed_tasks_jsonb",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("adherence_pct", sa.Float(), nullable=False, server_default="0"),
        sa.Column("consecutive_miss_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("alerted_at", sa.DateTime(timezone=True), nullable=True),
        *_audit_cols(),
        sa.ForeignKeyConstraint(
            ["study_plan_id"], [f"{_SCHEMA}.study_plans.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint("study_plan_id", "day_date", name="study_plan_days_plan_date_uq"),
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_study_plan_days_study_plan_id",
        "study_plan_days",
        ["study_plan_id"],
        schema=_SCHEMA,
    )

    op.create_table(
        "reminder_preferences",
        sa.Column("student_user_id", sa.String(length=36), primary_key=True),
        sa.Column("push_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "email_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "sms_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "timezone",
            sa.String(length=64),
            nullable=False,
            server_default="Asia/Karachi",
        ),
        *_audit_cols(),
        sa.ForeignKeyConstraint(["student_user_id"], [f"{_SCHEMA}.users.id"], ondelete="CASCADE"),
        schema=_SCHEMA,
    )


def downgrade() -> None:
    op.drop_table("reminder_preferences", schema=_SCHEMA)
    op.drop_index(
        "ix_study_plan_days_study_plan_id",
        table_name="study_plan_days",
        schema=_SCHEMA,
    )
    op.drop_table("study_plan_days", schema=_SCHEMA)
    op.drop_index(
        "ix_study_plan_items_study_plan_id",
        table_name="study_plan_items",
        schema=_SCHEMA,
    )
    op.drop_table("study_plan_items", schema=_SCHEMA)
    op.drop_index("ix_study_plans_deleted_at", table_name="study_plans", schema=_SCHEMA)
    op.drop_index(
        "ix_study_plans_subscription_tier_id",
        table_name="study_plans",
        schema=_SCHEMA,
    )
    op.drop_index("ix_study_plans_exam_type_id", table_name="study_plans", schema=_SCHEMA)
    op.drop_index("ix_study_plans_student_user_id", table_name="study_plans", schema=_SCHEMA)
    op.drop_table("study_plans", schema=_SCHEMA)
    op.drop_index(
        "ix_prep_book_topics_curriculum_topic_id",
        table_name="prep_book_topics",
        schema=_SCHEMA,
    )
    op.drop_index(
        "ix_prep_book_topics_student_material_id",
        table_name="prep_book_topics",
        schema=_SCHEMA,
    )
    op.drop_table("prep_book_topics", schema=_SCHEMA)
    op.drop_index(
        "ix_student_goals_student_user_id",
        table_name="student_goals",
        schema=_SCHEMA,
    )
    op.drop_table("student_goals", schema=_SCHEMA)
    op.drop_index(
        "ix_student_materials_deleted_at",
        table_name="student_materials",
        schema=_SCHEMA,
    )
    op.drop_index(
        "ix_student_materials_student_user_id",
        table_name="student_materials",
        schema=_SCHEMA,
    )
    op.drop_table("student_materials", schema=_SCHEMA)
    for name in (
        "study_plan_items_granularity_enum",
        "study_plans_granularity_current_enum",
        "study_plans_status_enum",
        "student_materials_book_type_enum",
        "student_materials_source_type_enum",
        "self_study_tenant_type_enum",
    ):
        op.execute(f"DROP TYPE IF EXISTS {_SCHEMA}.{name}")
