"""Widen Authentik-sub columns in TOS tables from VARCHAR(36) to VARCHAR(255).

VARCHAR(36) was sized for plain UUIDs, but Authentik's sub/JWT claim can be longer.
Matches the width already used by users.authentik_id (VARCHAR(255)).

Affected columns:
  school.user_tos_acceptances.user_id
  school.tos_versions.published_by
  school.disclaimer_versions.published_by

Revision ID: school_0011
Revises: school_0010
Create Date: 2026-06-03

"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "school_0011"
down_revision: str = "school_0010"
branch_labels: tuple[()] = ()
depends_on: str | None = None


def upgrade() -> None:
    op.alter_column(
        "user_tos_acceptances",
        "user_id",
        existing_type=sa.String(36),
        type_=sa.String(255),
        schema="school",
    )
    op.alter_column(
        "tos_versions",
        "published_by",
        existing_type=sa.String(36),
        type_=sa.String(255),
        existing_nullable=True,
        schema="school",
    )
    op.alter_column(
        "disclaimer_versions",
        "published_by",
        existing_type=sa.String(36),
        type_=sa.String(255),
        existing_nullable=True,
        schema="school",
    )


def downgrade() -> None:
    op.alter_column(
        "disclaimer_versions",
        "published_by",
        existing_type=sa.String(255),
        type_=sa.String(36),
        existing_nullable=True,
        schema="school",
    )
    op.alter_column(
        "tos_versions",
        "published_by",
        existing_type=sa.String(255),
        type_=sa.String(36),
        existing_nullable=True,
        schema="school",
    )
    op.alter_column(
        "user_tos_acceptances",
        "user_id",
        existing_type=sa.String(255),
        type_=sa.String(36),
        schema="school",
    )
