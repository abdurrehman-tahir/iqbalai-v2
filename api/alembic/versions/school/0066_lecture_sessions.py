"""School migration: student lecture study sessions (T-151).

Revision ID: school_0066
Revises: school_0065
Create Date: 2026-09-21

Purpose: lecture_sessions (school) — Flow 6 §3.1 session lifecycle.
Independent learners use self_study_sessions (Flow 8); no independent
mirror in this revision.
Risk: low — additive table + enums only.
Reversible: yes
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "school_0066"
down_revision: str = "school_0065"
branch_labels: tuple[()] = ()
depends_on: str | None = None

_SCHEMA = "school"
_MODE_VALUES = ("text", "voice")
_STATUS_VALUES = ("active", "ended")


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
            "WHERE table_schema = :schema AND table_name = 'lecture_sessions'"
        ),
        {"schema": _SCHEMA},
    ).scalar():
        return

    _create_enum_if_missing(
        f"{_SCHEMA}.lecture_sessions_mode_enum",
        ", ".join(f"'{v}'" for v in _MODE_VALUES),
    )
    _create_enum_if_missing(
        f"{_SCHEMA}.lecture_sessions_status_enum",
        ", ".join(f"'{v}'" for v in _STATUS_VALUES),
    )

    mode_enum = postgresql.ENUM(
        *_MODE_VALUES,
        name="lecture_sessions_mode_enum",
        schema=_SCHEMA,
        create_type=False,
    )
    status_enum = postgresql.ENUM(
        *_STATUS_VALUES,
        name="lecture_sessions_status_enum",
        schema=_SCHEMA,
        create_type=False,
    )
    # Reuse lectures_tenant_type_enum created by school_0051 — do not CREATE TYPE.
    tenant_type_enum = postgresql.ENUM(
        "school",
        "independent",
        name="lectures_tenant_type_enum",
        schema=_SCHEMA,
        create_type=False,
    )

    op.create_table(
        "lecture_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "lecture_id",
            sa.String(36),
            sa.ForeignKey(f"{_SCHEMA}.lectures.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "student_user_id",
            sa.String(36),
            sa.ForeignKey(f"{_SCHEMA}.users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tenant_type", tenant_type_enum, nullable=False, server_default="school"),
        sa.Column("mode", mode_enum, nullable=False, server_default="text"),
        sa.Column("status", status_enum, nullable=False, server_default="active"),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_lecture_sessions_lecture_id",
        "lecture_sessions",
        ["lecture_id"],
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_lecture_sessions_student_user_id",
        "lecture_sessions",
        ["student_user_id"],
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_lecture_sessions_status_last_activity_at",
        "lecture_sessions",
        ["status", "last_activity_at"],
        schema=_SCHEMA,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_lecture_sessions_status_last_activity_at",
        table_name="lecture_sessions",
        schema=_SCHEMA,
    )
    op.drop_index(
        "ix_lecture_sessions_student_user_id",
        table_name="lecture_sessions",
        schema=_SCHEMA,
    )
    op.drop_index(
        "ix_lecture_sessions_lecture_id",
        table_name="lecture_sessions",
        schema=_SCHEMA,
    )
    op.drop_table("lecture_sessions", schema=_SCHEMA)
    op.execute(f"DROP TYPE IF EXISTS {_SCHEMA}.lecture_sessions_status_enum")
    op.execute(f"DROP TYPE IF EXISTS {_SCHEMA}.lecture_sessions_mode_enum")
