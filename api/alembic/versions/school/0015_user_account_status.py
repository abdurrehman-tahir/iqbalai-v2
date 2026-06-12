"""Add user account status column for lifecycle management.

Revision ID: school_0015
Revises: school_0014
Create Date: 2026-06-12

T-033 (M-02): ACTIVE / SUSPENDED / DEACTIVATED lifecycle per flow-2 §3.5.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "school_0015"
down_revision: str = "school_0014"
branch_labels: tuple[()] = ()
depends_on: str | None = None


def upgrade() -> None:
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
