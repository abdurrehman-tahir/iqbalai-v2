"""School migration: lecture_edit_sessions table (T-129, Flow 5 §3.5 #31).

Revision ID: school_0058
Revises: school_0057
Create Date: 2026-09-11

Purpose: per-edit-session effort tracking (active_ms/edits_count/char_delta)
feeding the T-133 effort score and the T-134 scoring pipeline.
Risk: low — additive table only.
Reversible: yes
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "school_0058"
down_revision: str = "school_0057"
branch_labels: tuple[()] = ()
depends_on: str | None = None

_SCHEMA = "school"


def upgrade() -> None:
    op.create_table(
        "lecture_edit_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "lecture_version_id",
            sa.String(36),
            sa.ForeignKey(f"{_SCHEMA}.lecture_versions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "teacher_user_id",
            sa.String(36),
            sa.ForeignKey(f"{_SCHEMA}.users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("active_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("edits_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("char_delta", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("(now() AT TIME ZONE 'UTC')"),
        ),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("active_ms >= 0", name="lecture_edit_sessions_active_ms_nonneg_check"),
        sa.CheckConstraint(
            "edits_count >= 0", name="lecture_edit_sessions_edits_count_nonneg_check"
        ),
        sa.CheckConstraint("char_delta >= 0", name="lecture_edit_sessions_char_delta_nonneg_check"),
        sa.CheckConstraint(
            "ended_at IS NULL OR ended_at >= started_at",
            name="lecture_edit_sessions_ended_after_started_check",
        ),
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_lecture_edit_sessions_lecture_version_id",
        "lecture_edit_sessions",
        ["lecture_version_id"],
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_lecture_edit_sessions_teacher_user_id",
        "lecture_edit_sessions",
        ["teacher_user_id"],
        schema=_SCHEMA,
    )


def downgrade() -> None:
    op.drop_table("lecture_edit_sessions", schema=_SCHEMA)
