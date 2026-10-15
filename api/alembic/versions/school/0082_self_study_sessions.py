"""School migration: self_study_sessions (T-210).

Revision ID: school_0082
Revises: school_0081
Create Date: 2026-10-15
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "school_0082"
down_revision: str = "school_0081"
branch_labels: tuple[()] = ()
depends_on: str | None = None

_SCHEMA = "school"


def upgrade() -> None:
    op.execute(
        f"""
        DO $$ BEGIN
            CREATE TYPE {_SCHEMA}.self_study_sessions_status_enum AS ENUM ('active', 'ended');
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$;
        """
    )
    status = postgresql.ENUM(
        "active",
        "ended",
        name="self_study_sessions_status_enum",
        schema=_SCHEMA,
        create_type=False,
    )
    tenant = postgresql.ENUM(
        "school",
        "independent",
        name="self_study_tenant_type_enum",
        schema=_SCHEMA,
        create_type=False,
    )
    op.create_table(
        "self_study_sessions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_type", tenant, nullable=False),
        sa.Column("student_user_id", sa.String(length=36), nullable=False),
        sa.Column("mode", sa.String(length=32), nullable=False, server_default="self_study"),
        sa.Column("status", status, nullable=False, server_default="active"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("material_id", sa.String(length=36), nullable=True),
        sa.Column("study_plan_id", sa.String(length=36), nullable=True),
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
        sa.ForeignKeyConstraint(["student_user_id"], [f"{_SCHEMA}.users.id"], ondelete="CASCADE"),
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_self_study_sessions_student_user_id",
        "self_study_sessions",
        ["student_user_id"],
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_self_study_sessions_material_id",
        "self_study_sessions",
        ["material_id"],
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_self_study_sessions_study_plan_id",
        "self_study_sessions",
        ["study_plan_id"],
        schema=_SCHEMA,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_self_study_sessions_study_plan_id",
        table_name="self_study_sessions",
        schema=_SCHEMA,
    )
    op.drop_index(
        "ix_self_study_sessions_material_id",
        table_name="self_study_sessions",
        schema=_SCHEMA,
    )
    op.drop_index(
        "ix_self_study_sessions_student_user_id",
        table_name="self_study_sessions",
        schema=_SCHEMA,
    )
    op.drop_table("self_study_sessions", schema=_SCHEMA)
    op.execute(f"DROP TYPE IF EXISTS {_SCHEMA}.self_study_sessions_status_enum")
