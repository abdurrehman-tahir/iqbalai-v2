"""School migration: grade_promotion_requests (T-250).

Revision ID: school_0080
Revises: school_0079
Create Date: 2026-10-15

Purpose: Flow 2 §3.4 / ARCH §6.21 promotion request table + status enum
(pending_approval → approved → executing → executed | rejected | expired | failed).
Risk: low — additive table + enum on school schema only.
Reversible: yes

Model-first from GradePromotionRequest; enum created outside create_table
(AUDIT_LOG [migration-enum-create]).
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "school_0080"
down_revision: str = "school_0079"
branch_labels: tuple[()] = ()
depends_on: str | None = None

_SCHEMA = "school"
_ENUM_NAME = "grade_promotion_request_status"
_ENUM_VALUES = (
    "pending_approval",
    "approved",
    "rejected",
    "executing",
    "executed",
    "expired",
    "failed",
)


def upgrade() -> None:
    # Idempotent CREATE TYPE — never sa.Enum inside create_table (AUDIT_LOG).
    values_sql = ", ".join(f"'{v}'" for v in _ENUM_VALUES)
    op.execute(
        sa.text(
            f"""
            DO $$ BEGIN
                CREATE TYPE {_SCHEMA}.{_ENUM_NAME} AS ENUM ({values_sql});
            EXCEPTION
                WHEN duplicate_object THEN NULL;
            END $$;
            """
        )
    )

    status_enum = postgresql.ENUM(
        *_ENUM_VALUES,
        name=_ENUM_NAME,
        schema=_SCHEMA,
        create_type=False,
    )

    op.create_table(
        "grade_promotion_requests",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("school_id", sa.String(length=36), nullable=False),
        sa.Column("initiating_grade_id", sa.String(length=36), nullable=False),
        sa.Column("target_grade_id", sa.String(length=36), nullable=True),
        sa.Column("target_academic_session", sa.String(length=50), nullable=False),
        sa.Column("target_grade_name", sa.String(length=200), nullable=False),
        sa.Column("initiated_by_coordinator_id", sa.String(length=36), nullable=False),
        sa.Column(
            "exclusion_list_jsonb",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "status",
            status_enum,
            nullable=False,
            server_default="pending_approval",
        ),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column(
            "retry_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
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
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["school_id"], ["school.schools.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["initiating_grade_id"], ["school.grades.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["target_grade_id"], ["school.grades.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["initiated_by_coordinator_id"],
            ["school.users.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["approved_by_user_id"], ["school.users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        schema=_SCHEMA,
    )

    op.create_index(
        "grade_promotion_requests_pending_grade_uq",
        "grade_promotion_requests",
        ["initiating_grade_id"],
        unique=True,
        schema=_SCHEMA,
        postgresql_where=sa.text("status = 'pending_approval' AND deleted_at IS NULL"),
    )
    for name, cols in (
        ("ix_grade_promotion_requests_school_id", ["school_id"]),
        ("ix_grade_promotion_requests_initiating_grade_id", ["initiating_grade_id"]),
        ("ix_grade_promotion_requests_target_grade_id", ["target_grade_id"]),
        ("ix_grade_promotion_requests_status", ["status"]),
        (
            "ix_grade_promotion_requests_initiated_by_coordinator_id",
            ["initiated_by_coordinator_id"],
        ),
        ("ix_grade_promotion_requests_approved_by_user_id", ["approved_by_user_id"]),
        ("ix_grade_promotion_requests_deleted_at", ["deleted_at"]),
    ):
        op.create_index(name, "grade_promotion_requests", cols, schema=_SCHEMA)


def downgrade() -> None:
    for name in (
        "ix_grade_promotion_requests_deleted_at",
        "ix_grade_promotion_requests_approved_by_user_id",
        "ix_grade_promotion_requests_initiated_by_coordinator_id",
        "ix_grade_promotion_requests_status",
        "ix_grade_promotion_requests_target_grade_id",
        "ix_grade_promotion_requests_initiating_grade_id",
        "ix_grade_promotion_requests_school_id",
        "grade_promotion_requests_pending_grade_uq",
    ):
        op.drop_index(name, table_name="grade_promotion_requests", schema=_SCHEMA)
    op.drop_table("grade_promotion_requests", schema=_SCHEMA)
    op.execute(sa.text(f"DROP TYPE IF EXISTS {_SCHEMA}.{_ENUM_NAME}"))
