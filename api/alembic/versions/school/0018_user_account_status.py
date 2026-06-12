"""Add user account status column for lifecycle management.

Revision ID: school_0018
Revises: school_0017
Create Date: 2026-06-12

T-033 (M-02): ACTIVE / SUSPENDED / DEACTIVATED lifecycle per flow-2 §3.5.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "school_0018"
down_revision: str = "school_0017"
branch_labels: tuple[()] = ()
depends_on: str | None = None


def upgrade() -> None:
    conn = op.get_bind()
    status_col = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema = 'school' AND table_name = 'users' AND column_name = 'status'"
        )
    ).scalar()
    if status_col:
        return

    # Dev DBs may have a legacy account_status column + accountstatus enum from pre-migration drift.
    legacy_col = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema = 'school' AND table_name = 'users' AND column_name = 'account_status'"
        )
    ).scalar()
    if legacy_col:
        op.execute("ALTER TYPE school.accountstatus ADD VALUE IF NOT EXISTS 'deactivated'")
        op.execute("ALTER TYPE school.accountstatus RENAME TO useraccountstatus")
        op.alter_column("users", "account_status", new_column_name="status", schema="school")
        op.create_index("ix_users_status", "users", ["status"], schema="school")
        return

    op.execute(
        "CREATE TYPE school.useraccountstatus AS ENUM ('active', 'suspended', 'deactivated')"
    )
    op.add_column(
        "users",
        sa.Column(
            "status",
            sa.Enum(
                "active",
                "suspended",
                "deactivated",
                name="useraccountstatus",
                schema="school",
                create_type=False,
            ),
            nullable=False,
            server_default="active",
        ),
        schema="school",
    )
    op.create_index("ix_users_status", "users", ["status"], schema="school")


def downgrade() -> None:
    op.drop_index("ix_users_status", table_name="users", schema="school")
    op.drop_column("users", "status", schema="school")
    op.execute("DROP TYPE IF EXISTS school.useraccountstatus")
