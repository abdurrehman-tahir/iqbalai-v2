"""Add notifications table with RLS (T-023).

Per ARCH §9.21: 7 locked namespaces. 90-day TTL cleanup via Celery beat (Phase 2).

Revision ID: school_0008
Revises: school_0007
Create Date: 2026-05-25


Purpose: Add in-app notifications table.
Risk: low
Reversible: yes
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "school_0008"
down_revision: str = "school_0007"
branch_labels: tuple[()] = ()
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("recipient_user_id", sa.String(36), nullable=False),
        # 7 locked namespaces per ARCH §9.21
        sa.Column("feature_namespace", sa.String(50), nullable=False),
        # e.g. "account.invite_sent", "quiz.grade_released"
        sa.Column("template_key", sa.String(100), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        # Extra payload stored as JSON string — parsed at read time
        sa.Column("metadata_json", sa.Text, nullable=True),
        sa.Column("is_read", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        # Tenant scoping — NULL for platform-level notifications
        sa.Column("school_id", sa.String(36), nullable=True),
        # AuditMixin columns
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        # SoftDeleteMixin — used by Celery beat 90-day TTL sweep (Phase 2)
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        schema="school",
    )

    op.create_index(
        "ix_notifications_recipient",
        "notifications",
        ["recipient_user_id"],
        schema="school",
    )
    op.create_index(
        "ix_notifications_namespace",
        "notifications",
        ["feature_namespace"],
        schema="school",
    )
    op.create_index(
        "ix_notifications_is_read",
        "notifications",
        ["is_read"],
        schema="school",
    )
    op.create_index(
        "ix_notifications_school_id",
        "notifications",
        ["school_id"],
        schema="school",
    )

    # RLS: callers see only their tenant's notifications (or platform-wide ones).
    # Platform admin sees all rows (bypasses school_id filter).
    op.execute("ALTER TABLE school.notifications FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY notifications_isolation ON school.notifications
        USING (
            current_setting('app.current_role', true) = 'platform_admin'
            OR school_id = current_setting('app.current_school_id', true)
            OR school_id IS NULL
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS notifications_isolation ON school.notifications")

    op.drop_index("ix_notifications_school_id", table_name="notifications", schema="school")
    op.drop_index("ix_notifications_is_read", table_name="notifications", schema="school")
    op.drop_index("ix_notifications_namespace", table_name="notifications", schema="school")
    op.drop_index("ix_notifications_recipient", table_name="notifications", schema="school")

    op.drop_table("notifications", schema="school")
