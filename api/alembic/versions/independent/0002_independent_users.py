"""Add users table to independent schema.

Revision ID: independent_0002
Revises: independent_0001
Create Date: 2026-06-22

Purpose: Independent teacher/student accounts for M-05 T-069.
Risk: low
Reversible: yes
"""

from __future__ import annotations

from sqlalchemy import inspect, text

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

    # Raw SQL avoids SQLAlchemy re-issuing CREATE TYPE on sa.Enum columns.
    op.execute(
        text(
            """
            CREATE TABLE independent.users (
                id VARCHAR(36) PRIMARY KEY,
                authentik_id VARCHAR(255) NOT NULL UNIQUE,
                email VARCHAR(255) NOT NULL,
                display_name VARCHAR(255) NOT NULL,
                role independent.independentuserrole NOT NULL,
                status independent.independentuseraccountstatus NOT NULL DEFAULT 'active',
                language_preference VARCHAR(10) NOT NULL DEFAULT 'en',
                created_at TIMESTAMPTZ NOT NULL DEFAULT (now() AT TIME ZONE 'UTC'),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT (now() AT TIME ZONE 'UTC'),
                deleted_at TIMESTAMPTZ
            )
            """
        )
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
