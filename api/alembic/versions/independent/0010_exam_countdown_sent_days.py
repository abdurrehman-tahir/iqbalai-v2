"""Independent migration: exam countdown tracking on student profiles (T-107).

Revision ID: independent_0010
Revises: independent_0009
Create Date: 2026-07-28

Purpose: exam_countdown_sent_days for independent exam-date countdown / passed notifs.
Risk: low
Reversible: yes
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "independent_0010"
down_revision: str = "independent_0009"
branch_labels: tuple[()] = ()
depends_on: str | None = None


def upgrade() -> None:
    conn = op.get_bind()
    exists = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema = 'independent' "
            "AND table_name = 'independent_student_profiles' "
            "AND column_name = 'exam_countdown_sent_days'"
        )
    ).scalar()
    if exists:
        return
    op.add_column(
        "independent_student_profiles",
        sa.Column("exam_countdown_sent_days", sa.String(length=32), nullable=True),
        schema="independent",
    )


def downgrade() -> None:
    op.drop_column(
        "independent_student_profiles",
        "exam_countdown_sent_days",
        schema="independent",
    )
