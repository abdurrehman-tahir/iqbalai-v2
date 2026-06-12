"""Widen Authentik-sub actor columns from VARCHAR(36) to VARCHAR(255).

Authentik JWT `sub` claims can exceed 36 characters (e.g. 64-char hashes).
Matches users.authentik_id width (school_0002) and TOS widen (school_0011).

Affected columns:
  school.upload_records.uploaded_by
  school.audit_log.actor_id
  school.notifications.recipient_user_id

Revision ID: school_0014
Revises: school_0013
Create Date: 2026-06-11

Purpose: Fix library upload 500 when storing JWT sub in uploaded_by.
Risk: low
Reversible: yes
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "school_0014"
down_revision: str = "school_0013"
branch_labels: tuple[()] = ()
depends_on: str | None = None


def upgrade() -> None:
    op.alter_column(
        "upload_records",
        "uploaded_by",
        existing_type=sa.String(36),
        type_=sa.String(255),
        existing_nullable=True,
        schema="school",
    )
    op.alter_column(
        "audit_log",
        "actor_id",
        existing_type=sa.String(36),
        type_=sa.String(255),
        existing_nullable=True,
        schema="school",
    )
    op.alter_column(
        "notifications",
        "recipient_user_id",
        existing_type=sa.String(36),
        type_=sa.String(255),
        existing_nullable=False,
        schema="school",
    )


def downgrade() -> None:
    op.alter_column(
        "notifications",
        "recipient_user_id",
        existing_type=sa.String(255),
        type_=sa.String(36),
        existing_nullable=False,
        schema="school",
    )
    op.alter_column(
        "audit_log",
        "actor_id",
        existing_type=sa.String(255),
        type_=sa.String(36),
        existing_nullable=True,
        schema="school",
    )
    op.alter_column(
        "upload_records",
        "uploaded_by",
        existing_type=sa.String(255),
        type_=sa.String(36),
        existing_nullable=True,
        schema="school",
    )
