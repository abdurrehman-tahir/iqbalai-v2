"""Independent migration: session_difficulty_log (T-175).

Revision ID: independent_0020
Revises: independent_0019
Create Date: 2026-09-29
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "independent_0020"
down_revision: str = "independent_0019"
branch_labels: tuple[()] = ()
depends_on: str | None = None

_SCHEMA = "independent"


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
            "WHERE table_schema = :schema AND table_name = 'session_difficulty_log'"
        ),
        {"schema": _SCHEMA},
    ).scalar():
        return

    _create_enum_if_missing(
        f"{_SCHEMA}.session_difficulty_log_tenant_type_enum",
        "'school', 'independent'",
    )
    tenant_type_enum = postgresql.ENUM(
        "school",
        "independent",
        name="session_difficulty_log_tenant_type_enum",
        schema=_SCHEMA,
        create_type=False,
    )
    op.create_table(
        "session_difficulty_log",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("sub_topic_id", sa.String(length=128), nullable=False),
        sa.Column("question_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "tried_angles",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("last_angle", sa.String(length=64), nullable=True),
        sa.Column("tenant_type", tenant_type_enum, nullable=False),
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
        sa.UniqueConstraint(
            "session_id",
            "sub_topic_id",
            name="ind_session_difficulty_log_session_subtopic_uq",
        ),
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_ind_session_difficulty_log_session_id",
        "session_difficulty_log",
        ["session_id"],
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_ind_session_difficulty_log_sub_topic_id",
        "session_difficulty_log",
        ["sub_topic_id"],
        schema=_SCHEMA,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_ind_session_difficulty_log_sub_topic_id",
        table_name="session_difficulty_log",
        schema=_SCHEMA,
    )
    op.drop_index(
        "ix_ind_session_difficulty_log_session_id",
        table_name="session_difficulty_log",
        schema=_SCHEMA,
    )
    op.drop_table("session_difficulty_log", schema=_SCHEMA)
