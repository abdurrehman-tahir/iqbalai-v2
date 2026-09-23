"""Add school.user_settings.teacher_activity_share for #72 (T-162 / M-12).

Revision ID: school_0069
Revises: school_0068
Create Date: 2026-09-21

Purpose: Lecture-Q&A-facing privacy preference (share | private), default share
(Open Q12). Reuses school.user_settings (T-101) rather than a new table.

BLOCKED-HOOK / ownership: Flow 8 / M-17 T-220 is the CANONICAL owner of #72
storage long-term (``student_self_study_privacy``). M-12 ships this column as
the lecture-Q&A-facing preference; M-17 must reconcile to the same
``teacher_activity_share`` column (or migrate into it) — do not invent a second
#72 store. Independent schema: #72 is hidden (N/A) — no independent migration.

Risk: low — additive enum + column with server default.
Reversible: yes
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "school_0069"
down_revision: str = "school_0068"
branch_labels: tuple[()] = ()
depends_on: str | None = None

_SCHEMA = "school"
_ENUM_NAME = "user_settings_teacher_activity_share_enum"


def upgrade() -> None:
    op.execute(f"CREATE TYPE {_SCHEMA}.{_ENUM_NAME} AS ENUM ('share', 'private')")
    share_enum = postgresql.ENUM(
        "share",
        "private",
        name=_ENUM_NAME,
        schema=_SCHEMA,
        create_type=False,
    )
    op.add_column(
        "user_settings",
        sa.Column(
            "teacher_activity_share",
            share_enum,
            nullable=False,
            server_default="share",
        ),
        schema=_SCHEMA,
    )


def downgrade() -> None:
    op.drop_column("user_settings", "teacher_activity_share", schema=_SCHEMA)
    op.execute(f"DROP TYPE IF EXISTS {_SCHEMA}.{_ENUM_NAME}")
