"""School migration: student_events analytics store (T-174).

Revision ID: school_0071
Revises: school_0070
Create Date: 2026-09-29

Purpose: long-term student.lecture.* persistence for Analytics Consumer.
Risk: low — additive table + enum.
Reversible: yes
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "school_0071"
down_revision: str = "school_0070"
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


def upgrade() -> None:
    conn = op.get_bind()
    if conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = :schema AND table_name = 'student_events'"
        ),
        {"schema": _SCHEMA},
    ).scalar():
        return

    _create_enum_if_missing(
        f"{_SCHEMA}.student_events_tenant_type_enum",
        "'school', 'independent'",
    )
    tenant_type_enum = postgresql.ENUM(
        "school",
        "independent",
        name="student_events_tenant_type_enum",
        schema=_SCHEMA,
        create_type=False,
    )
    op.create_table(
        "student_events",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("tenant_type", tenant_type_enum, nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=True),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=True),
        sa.Column("lecture_id", sa.String(length=36), nullable=True),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column(
            "event_payload_jsonb",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        schema=_SCHEMA,
    )
    op.create_index("ix_student_events_tenant_id", "student_events", ["tenant_id"], schema=_SCHEMA)
    op.create_index("ix_student_events_user_id", "student_events", ["user_id"], schema=_SCHEMA)
    op.create_index(
        "ix_student_events_session_id", "student_events", ["session_id"], schema=_SCHEMA
    )
    op.create_index(
        "ix_student_events_event_type", "student_events", ["event_type"], schema=_SCHEMA
    )
    op.create_index(
        "ix_student_events_occurred_at", "student_events", ["occurred_at"], schema=_SCHEMA
    )


def downgrade() -> None:
    op.drop_index("ix_student_events_occurred_at", table_name="student_events", schema=_SCHEMA)
    op.drop_index("ix_student_events_event_type", table_name="student_events", schema=_SCHEMA)
    op.drop_index("ix_student_events_session_id", table_name="student_events", schema=_SCHEMA)
    op.drop_index("ix_student_events_user_id", table_name="student_events", schema=_SCHEMA)
    op.drop_index("ix_student_events_tenant_id", table_name="student_events", schema=_SCHEMA)
    op.drop_table("student_events", schema=_SCHEMA)
