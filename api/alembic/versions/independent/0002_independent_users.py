"""Add users table to independent schema.

Revision ID: independent_0002
Revises: independent_0001
Create Date: 2026-06-22

Purpose: Independent teacher/student accounts for M-05 T-069.
Risk: low
Reversible: yes
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

revision: str = "independent_0002"
down_revision: str = "independent_0001"
branch_labels: tuple[()] = ()
depends_on: str | None = None


def _ensure_enum(schema: str, name: str, values: str) -> None:
    """Create a Postgres enum if missing (safe after a failed partial migration)."""
    op.execute(
        f"""
        DO $$ BEGIN
            CREATE TYPE {schema}.{name} AS ENUM ({values});
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$;
        """
    )


def upgrade() -> None:
    _ensure_enum(
        "independent",
        "independentuserrole",
        "'independent_teacher', 'independent_student'",
    )
    _ensure_enum(
        "independent",
        "independentuseraccountstatus",
        "'active', 'suspended', 'deactivated'",
    )

    bind = op.get_bind()
    if inspect(bind).has_table("users", schema="independent"):
        return

    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("authentik_id", sa.String(255), nullable=False, unique=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column(
            "role",
            sa.Enum(
                "independent_teacher",
                "independent_student",
                name="independentuserrole",
                schema="independent",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "active",
                "suspended",
                "deactivated",
                name="independentuseraccountstatus",
                schema="independent",
                create_type=False,
            ),
            nullable=False,
            server_default="active",
        ),
        sa.Column("language_preference", sa.String(10), nullable=False, server_default="en"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        schema="independent",
    )
    op.create_index(
        "ix_independent_users_authentik_id",
        "users",
        ["authentik_id"],
        unique=True,
        schema="independent",
    )
    op.create_index(
        "ix_independent_users_email",
        "users",
        ["email"],
        schema="independent",
    )
    op.create_index(
        "ix_independent_users_deleted_at",
        "users",
        ["deleted_at"],
        schema="independent",
    )


def downgrade() -> None:
    op.drop_index("ix_independent_users_deleted_at", table_name="users", schema="independent")
    op.drop_index("ix_independent_users_email", table_name="users", schema="independent")
    op.drop_index("ix_independent_users_authentik_id", table_name="users", schema="independent")
    op.drop_table("users", schema="independent")
    op.execute("DROP TYPE IF EXISTS independent.independentuseraccountstatus")
    op.execute("DROP TYPE IF EXISTS independent.independentuserrole")
