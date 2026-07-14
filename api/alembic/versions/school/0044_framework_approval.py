"""Framework study-plan approval columns — reviewer notes + SLA tracking.

Revision ID: school_0044
Revises: school_0043
Create Date: 2026-07-06

T-094 (M-07): the PENDING_APPROVAL -> PUBLISHED approval workflow (Flow 4 §3.5.1,
ARCH §3.19). Adds two additive columns to framework_study_plans:
- reviewer_notes: captured when a Platform Admin rejects a plan back to DRAFT.
- sla_reminders_sent: comma-separated markers ("7,14") so the approval-SLA beat
  never re-fires the same reminder for a plan stuck in PENDING_APPROVAL.

Purpose: framework_study_plans.reviewer_notes + .sla_reminders_sent columns.
Risk: low
Reversible: yes
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "school_0044"
down_revision: str = "school_0043"
branch_labels: tuple[()] = ()
depends_on: str | None = None


def upgrade() -> None:
    conn = op.get_bind()
    existing = {
        row[0]
        for row in conn.execute(
            sa.text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = 'school' AND table_name = 'framework_study_plans'"
            )
        )
    }
    if "reviewer_notes" not in existing:
        op.add_column(
            "framework_study_plans",
            sa.Column("reviewer_notes", sa.Text(), nullable=True),
            schema="school",
        )
    if "sla_reminders_sent" not in existing:
        op.add_column(
            "framework_study_plans",
            sa.Column("sla_reminders_sent", sa.String(50), nullable=True),
            schema="school",
        )


def downgrade() -> None:
    op.drop_column("framework_study_plans", "sla_reminders_sent", schema="school")
    op.drop_column("framework_study_plans", "reviewer_notes", schema="school")
