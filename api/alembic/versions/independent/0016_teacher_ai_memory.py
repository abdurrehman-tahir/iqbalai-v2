"""Independent migration: teacher_ai_memory table (T-129, #36).

Revision ID: independent_0016
Revises: independent_0015
Create Date: 2026-09-11

Purpose: simplified own-memory variant for independent teachers (T-138).
Risk: low — additive table only.
Reversible: yes
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "independent_0016"
down_revision: str = "independent_0015"
branch_labels: tuple[()] = ()
depends_on: str | None = None

_SCHEMA = "independent"
_RESPONSE_VALUES = ("acted", "ignored", "none")


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
    response_list = ", ".join(f"'{v}'" for v in _RESPONSE_VALUES)
    _create_enum_if_missing(f"{_SCHEMA}.teacher_ai_memory_teacher_response_enum", response_list)

    response_enum = postgresql.ENUM(
        *_RESPONSE_VALUES,
        name="teacher_ai_memory_teacher_response_enum",
        schema=_SCHEMA,
        create_type=False,
    )

    op.create_table(
        "teacher_ai_memory",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_type", sa.String(20), nullable=False, server_default="independent"),
        sa.Column(
            "teacher_user_id",
            sa.String(36),
            sa.ForeignKey(f"{_SCHEMA}.users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("weakness_type", sa.String(100), nullable=False),
        sa.Column("frequency", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("last_suggestion", sa.Text(), nullable=False),
        sa.Column("teacher_response", response_enum, nullable=False, server_default="none"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("frequency >= 1", name="teacher_ai_memory_frequency_positive_check"),
        sa.UniqueConstraint(
            "teacher_user_id",
            "category",
            "weakness_type",
            name="teacher_ai_memory_teacher_category_weakness_uq",
        ),
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_teacher_ai_memory_teacher_user_id",
        "teacher_ai_memory",
        ["teacher_user_id"],
        schema=_SCHEMA,
    )


def downgrade() -> None:
    op.drop_table("teacher_ai_memory", schema=_SCHEMA)
    op.execute(f"DROP TYPE IF EXISTS {_SCHEMA}.teacher_ai_memory_teacher_response_enum")
