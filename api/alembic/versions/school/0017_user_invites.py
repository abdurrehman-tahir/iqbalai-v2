"""Add user_invites table for Path A admin invitation flow.

Revision ID: school_0017
Revises: school_0016
Create Date: 2026-06-12

T-030 (M-02 School Onboarding): Platform Admin invites District Admin via email
with a 7-day token. Tokens are stored hashed; raw token only appears in the email.

Purpose: Add user_invites table for Path A admin email invitation flow.
Risk: low
Reversible: yes
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "school_0017"
down_revision: str = "school_0016"
branch_labels: tuple[()] = ()
depends_on: str | None = None


def upgrade() -> None:
    conn = op.get_bind()
    if conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = 'school' AND table_name = 'user_invites'"
        )
    ).scalar():
        return

    op.create_table(
        "user_invites",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("invited_by_user_id", sa.String(255), nullable=False),
        # users.role is plain text in this schema; avoid re-creating school.userrole here.
        sa.Column("invited_role", sa.Text(), nullable=False),
        sa.Column(
            "district_id", sa.String(36), sa.ForeignKey("school.districts.id"), nullable=True
        ),
        sa.Column("school_id", sa.String(36), sa.ForeignKey("school.schools.id"), nullable=True),
        sa.Column("scope_ids_json", sa.JSON(), nullable=True),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("authentik_id", sa.String(255), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "accepted",
                "expired",
                "rejected",
                "locked",
                name="user_invite_status",
                schema="school",
                create_type=True,
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("resent_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rejected_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        schema="school",
    )

    op.create_index(
        "ix_user_invites_email",
        "user_invites",
        ["email"],
        schema="school",
    )
    op.create_index(
        "ix_user_invites_token_hash",
        "user_invites",
        ["token_hash"],
        unique=True,
        schema="school",
    )
    op.create_index(
        "ix_user_invites_status",
        "user_invites",
        ["status"],
        schema="school",
    )
    op.execute(
        """
        CREATE UNIQUE INDEX user_invites_email_pending_uq
        ON school.user_invites (email)
        WHERE status = 'pending'
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS school.user_invites_email_pending_uq")
    op.drop_index("ix_user_invites_status", table_name="user_invites", schema="school")
    op.drop_index("ix_user_invites_token_hash", table_name="user_invites", schema="school")
    op.drop_index("ix_user_invites_email", table_name="user_invites", schema="school")
    op.drop_table("user_invites", schema="school")
    op.execute("DROP TYPE IF EXISTS school.user_invite_status")
