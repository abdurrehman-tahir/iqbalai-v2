"""School migration: lecture voice session + turn tables (T-121, #25).

Revision ID: school_0053
Revises: school_0052
Create Date: 2026-08-04

Purpose: lecture_voice_sessions / lecture_voice_turns (school) — "Talk to AI"
voice conversation during lecture creation (flow-5 §3.4).
Risk: low — additive tables only.
Reversible: yes
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "school_0053"
down_revision: str = "school_0052"
branch_labels: tuple[()] = ()
depends_on: str | None = None

_SCHEMA = "school"
_STATUS_VALUES = ("active", "ended")


def _create_enum_if_missing(qualified_name: str, values_sql: str) -> None:
    # Idempotent CREATE TYPE — never emit CREATE TYPE via sa.Enum create_table
    # (AUDIT_LOG [migration-enum-create]).
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
    status_list = ", ".join(f"'{v}'" for v in _STATUS_VALUES)
    _create_enum_if_missing(f"{_SCHEMA}.lecture_voice_sessions_status_enum", status_list)

    status_enum = postgresql.ENUM(
        *_STATUS_VALUES,
        name="lecture_voice_sessions_status_enum",
        schema=_SCHEMA,
        create_type=False,
    )

    op.create_table(
        "lecture_voice_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "lecture_id",
            sa.String(36),
            sa.ForeignKey(f"{_SCHEMA}.lectures.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "teacher_user_id",
            sa.String(36),
            sa.ForeignKey(f"{_SCHEMA}.users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("status", status_enum, nullable=False, server_default="active"),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_lecture_voice_sessions_lecture_id",
        "lecture_voice_sessions",
        ["lecture_id"],
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_lecture_voice_sessions_teacher_user_id",
        "lecture_voice_sessions",
        ["teacher_user_id"],
        schema=_SCHEMA,
    )

    op.create_table(
        "lecture_voice_turns",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "session_id",
            sa.String(36),
            sa.ForeignKey(f"{_SCHEMA}.lecture_voice_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("transcript", sa.Text(), nullable=False),
        sa.Column("ai_response_text", sa.Text(), nullable=False),
        sa.Column("edit_operation_jsonb", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("audio_storage_key", sa.String(255), nullable=True),
        sa.Column("audio_purged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("session_id", "ordinal", name="lecture_voice_turns_session_ordinal_uq"),
        sa.CheckConstraint("ordinal >= 0", name="lecture_voice_turns_ordinal_nonneg_check"),
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_lecture_voice_turns_session_id",
        "lecture_voice_turns",
        ["session_id"],
        schema=_SCHEMA,
    )


def downgrade() -> None:
    op.drop_table("lecture_voice_turns", schema=_SCHEMA)
    op.drop_table("lecture_voice_sessions", schema=_SCHEMA)
    op.execute(f"DROP TYPE IF EXISTS {_SCHEMA}.lecture_voice_sessions_status_enum")
