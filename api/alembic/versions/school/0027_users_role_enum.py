"""Convert users.role from text to school.userrole enum.

Revision ID: school_0027
Revises: school_0026
Create Date: 2026-06-16

The ORM maps users.role as school.userrole, but school_0002 created the column as
plain text. Queries filtering by role (e.g. eligible teachers) fail with:
  operator does not exist: text = userrole

Purpose: Align DB column type with SQLAlchemy User.role mapping.
Risk: low
Reversible: yes
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "school_0027"
down_revision: str = "school_0026"
branch_labels: tuple[()] = ()
depends_on: str | None = None


def upgrade() -> None:
    conn = op.get_bind()
    udt = conn.execute(
        sa.text(
            "SELECT udt_name FROM information_schema.columns "
            "WHERE table_schema = 'school' AND table_name = 'users' AND column_name = 'role'"
        )
    ).scalar()
    if udt == "userrole":
        return

    op.execute("DROP VIEW IF EXISTS independent.users_readonly")
    op.execute(
        "ALTER TABLE school.users "
        "ALTER COLUMN role TYPE school.userrole "
        "USING role::school.userrole"
    )
    op.execute(
        """
        CREATE VIEW independent.users_readonly AS
        SELECT id, email, display_name, role, created_at
        FROM school.users
        WHERE deleted_at IS NULL
        """
    )


def downgrade() -> None:
    conn = op.get_bind()
    udt = conn.execute(
        sa.text(
            "SELECT udt_name FROM information_schema.columns "
            "WHERE table_schema = 'school' AND table_name = 'users' AND column_name = 'role'"
        )
    ).scalar()
    if udt == "text":
        return

    op.execute("DROP VIEW IF EXISTS independent.users_readonly")
    op.execute(
        "ALTER TABLE school.users "
        "ALTER COLUMN role TYPE text "
        "USING role::text"
    )
    op.execute(
        """
        CREATE VIEW independent.users_readonly AS
        SELECT id, email, display_name, role, created_at
        FROM school.users
        WHERE deleted_at IS NULL
        """
    )
