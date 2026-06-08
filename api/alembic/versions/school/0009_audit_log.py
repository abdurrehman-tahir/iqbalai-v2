"""Add audit_log table (T-025).

Per ARCH §14.10: every mutation is audit-logged. The table is intentionally
immutable — no UPDATE/DELETE at DB level. 7-year retention enforced via
Celery beat (Phase 2).

Revision ID: school_0009
Revises: school_0008
Create Date: 2026-05-25


Purpose: Add immutable audit_log table for platform mutations.
Risk: low
Reversible: yes
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "school_0009"
down_revision: str = "school_0008"
branch_labels: tuple[()] = ()
depends_on: str | None = None


def upgrade() -> None:
    # audit_log is intentionally immutable — no UPDATE/DELETE at DB level.
    # Rows are only ever INSERTed by the audit() helper in app/infrastructure/audit/log.py.
    op.create_table(
        "audit_log",
        sa.Column("id", sa.String(36), primary_key=True),
        # e.g. "user.created", "tos.published", "syllabus.updated"
        sa.Column("action", sa.String(100), nullable=False),
        # NULL when the action is system-initiated
        sa.Column("actor_id", sa.String(36), nullable=True),
        sa.Column("actor_role", sa.String(50), nullable=True),
        # e.g. "user", "tos_version", "exam_syllabus"
        sa.Column("target_type", sa.String(100), nullable=True),
        sa.Column("target_id", sa.String(36), nullable=True),
        # NULL for platform-level actions (no school context)
        sa.Column("school_id", sa.String(36), nullable=True),
        sa.Column("district_id", sa.String(36), nullable=True),
        # Extra context stored as JSON string
        sa.Column("metadata_json", sa.Text, nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        # No updated_at — audit rows are immutable by design
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        schema="school",
    )

    op.create_index(
        "ix_audit_log_actor_id",
        "audit_log",
        ["actor_id"],
        schema="school",
    )
    # Composite index for efficient target lookups (e.g. "all events for this tos_version")
    op.create_index(
        "ix_audit_log_target_type_target_id",
        "audit_log",
        ["target_type", "target_id"],
        schema="school",
    )
    op.create_index(
        "ix_audit_log_school_id",
        "audit_log",
        ["school_id"],
        schema="school",
    )
    # Time-range queries for the admin audit viewer
    op.create_index(
        "ix_audit_log_created_at",
        "audit_log",
        ["created_at"],
        schema="school",
    )


def downgrade() -> None:
    op.drop_index("ix_audit_log_created_at", table_name="audit_log", schema="school")
    op.drop_index("ix_audit_log_school_id", table_name="audit_log", schema="school")
    op.drop_index("ix_audit_log_target_type_target_id", table_name="audit_log", schema="school")
    op.drop_index("ix_audit_log_actor_id", table_name="audit_log", schema="school")

    op.drop_table("audit_log", schema="school")
