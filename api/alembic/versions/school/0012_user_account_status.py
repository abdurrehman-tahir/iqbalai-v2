"""Add account_status enum + column to users (ToS decline → SUSPENDED).

Revision ID: school_0012
Revises: school_0011
Create Date: 2026-06-08

Purpose: Track ACTIVE/SUSPENDED on users so ToS decline suspends the account per Flow 1 §5.6.
Risk: low
Reversible: yes
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "school_0012"
down_revision: str = "school_0011"
branch_labels: tuple[()] = ()
depends_on: str | None = None


def upgrade() -> None:
    op.execute("CREATE TYPE school.accountstatus AS ENUM ('active', 'suspended')")
    op.add_column(
        "users",
        sa.Column(
            "account_status",
            sa.Enum("active", "suspended", name="accountstatus", schema="school"),
            nullable=False,
            server_default="active",
        ),
        schema="school",
    )


def downgrade() -> None:
    op.drop_column("users", "account_status", schema="school")
    op.execute("DROP TYPE IF EXISTS school.accountstatus")
