"""Add exam_date to school student profiles.

Revision ID: school_0039
Revises: school_0038
Create Date: 2026-06-22

T-083 (M-06): deferrable exam date on student_profiles + countdown tracking.

Purpose: exam_date and exam_countdown_sent_days columns for Flow 4 §3.7.
Risk: low
Reversible: yes
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "school_0039"
down_revision: str = "school_0038"
branch_labels: tuple[()] = ()
depends_on: str | None = None


def upgrade() -> None:
    conn = op.get_bind()
    if conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema = 'school' AND table_name = 'student_profiles' "
            "AND column_name = 'exam_date'"
        )
    ).scalar():
        return

    op.add_column(
        "student_profiles",
        sa.Column("exam_date", sa.Date(), nullable=True),
        schema="school",
    )
    op.add_column(
        "student_profiles",
        sa.Column("exam_countdown_sent_days", sa.String(32), nullable=True),
        schema="school",
    )


def downgrade() -> None:
    op.drop_column("student_profiles", "exam_countdown_sent_days", schema="school")
    op.drop_column("student_profiles", "exam_date", schema="school")
