"""Add school.user_settings for Mode Switcher persistence (T-101).

Revision ID: school_0047
Revises: school_0046
Create Date: 2026-07-28

Purpose: Persist active Lecture/Self-Study mode + per-mode restore JSONB.
Risk: low
Reversible: yes
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "school_0047"
down_revision: str = "school_0046"
branch_labels: tuple[()] = ()
depends_on: str | None = None


def upgrade() -> None:
    conn = op.get_bind()
    if conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = 'school' AND table_name = 'user_settings'"
        )
    ).scalar():
        return

    op.execute(
        "CREATE TYPE school.user_settings_active_mode_enum AS ENUM ('lecture', 'self_study')"
    )

    active_mode = postgresql.ENUM(
        "lecture",
        "self_study",
        name="user_settings_active_mode_enum",
        schema="school",
        create_type=False,
    )

    op.create_table(
        "user_settings",
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("school.users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("active_mode", active_mode, nullable=False),
        sa.Column(
            "mode_state_jsonb",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text('\'{"lecture": {}, "self_study": {}}\'::jsonb'),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        schema="school",
    )
    op.create_index(
        "ix_user_settings_deleted_at",
        "user_settings",
        ["deleted_at"],
        schema="school",
    )


def downgrade() -> None:
    op.drop_index("ix_user_settings_deleted_at", table_name="user_settings", schema="school")
    op.drop_table("user_settings", schema="school")
    op.execute("DROP TYPE IF EXISTS school.user_settings_active_mode_enum")
