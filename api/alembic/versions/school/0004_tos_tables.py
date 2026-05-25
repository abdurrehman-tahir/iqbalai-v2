"""Add ToS, Disclaimer, and acceptance tables (T-016 + T-019).

Revision ID: school_0004
Revises: school_0003
Create Date: 2026-05-25

"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "school_0004"
down_revision: str = "school_0003"
branch_labels: tuple[()] = ()
depends_on: str | None = None


def upgrade() -> None:
    # ── tos_versions ─────────────────────────────────────────────────────────
    # Immutable; new version = new row. platform-wide (school_id IS NULL).
    op.create_table(
        "tos_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("version_number", sa.Integer, nullable=False),
        sa.Column("content_md", sa.Text, nullable=False),
        # English-only at launch; __TODO__ placeholders for ur/sd/ps per Flow 1 §9
        sa.Column("language", sa.String(10), nullable=False, server_default="en"),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_by", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        schema="school",
    )
    op.create_index(
        "ix_tos_versions_version_number",
        "tos_versions",
        ["version_number"],
        schema="school",
    )

    # ── disclaimer_versions ───────────────────────────────────────────────────
    # Same immutable pattern; 500-char limit enforced at application layer.
    op.create_table(
        "disclaimer_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("version_number", sa.Integer, nullable=False),
        sa.Column("content", sa.String(500), nullable=False),
        sa.Column("language", sa.String(10), nullable=False, server_default="en"),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_by", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        schema="school",
    )
    op.create_index(
        "ix_disclaimer_versions_version_number",
        "disclaimer_versions",
        ["version_number"],
        schema="school",
    )

    # ── user_tos_acceptances ──────────────────────────────────────────────────
    # One row per user per ToS version accepted.
    op.create_table(
        "user_tos_acceptances",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("tos_version_id", sa.String(36), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        schema="school",
    )
    op.create_index(
        "ix_user_tos_acceptances_user_id",
        "user_tos_acceptances",
        ["user_id"],
        schema="school",
    )
    op.create_index(
        "uq_user_tos_acceptance",
        "user_tos_acceptances",
        ["user_id", "tos_version_id"],
        unique=True,
        schema="school",
    )

    # ── Seed: ToS v1 (English placeholder) ───────────────────────────────────
    op.execute("""
        INSERT INTO school.tos_versions
            (id, version_number, content_md, language, effective_at, created_at, updated_at)
        VALUES (
            'tos-v1-000000000000-000000000000',
            1,
            '# IqbalAI Terms of Service\n\nVersion 1 — effective at launch.\n\n'
            '## 1. Acceptance\nBy using IqbalAI you agree to these terms.\n\n'
            '## 2. Platform Use\nIqbalAI is an AI-powered education platform. '
            'Use it responsibly and in accordance with your institution''s policies.\n\n'
            '## 3. Privacy\nWe collect and process educational data to deliver the service. '
            'See our Privacy Policy for details.\n\n'
            '## 4. Changes\nWe may update these terms. '
            'Continued use after update constitutes acceptance.\n\n'
            '__TODO__: Urdu, Sindhi, Pashto translations (Phase 2 per Flow 1 §9)',
            'en',
            NOW() AT TIME ZONE 'UTC',
            NOW() AT TIME ZONE 'UTC',
            NOW() AT TIME ZONE 'UTC'
        )
        ON CONFLICT DO NOTHING
    """)

    # ── Seed: Disclaimer v1 ───────────────────────────────────────────────────
    op.execute("""
        INSERT INTO school.disclaimer_versions
            (id, version_number, content, language, effective_at, created_at, updated_at)
        VALUES (
            'disc-v1-00000000000-000000000000',
            1,
            'AI-generated content may contain errors. Always verify with your teacher or '
            'official curriculum materials. IqbalAI is a supplementary learning tool.',
            'en',
            NOW() AT TIME ZONE 'UTC',
            NOW() AT TIME ZONE 'UTC',
            NOW() AT TIME ZONE 'UTC'
        )
        ON CONFLICT DO NOTHING
    """)


def downgrade() -> None:
    op.drop_index("uq_user_tos_acceptance", table_name="user_tos_acceptances", schema="school")
    op.drop_index(
        "ix_user_tos_acceptances_user_id",
        table_name="user_tos_acceptances",
        schema="school",
    )
    op.drop_table("user_tos_acceptances", schema="school")

    op.drop_index(
        "ix_disclaimer_versions_version_number",
        table_name="disclaimer_versions",
        schema="school",
    )
    op.drop_table("disclaimer_versions", schema="school")

    op.drop_index(
        "ix_tos_versions_version_number",
        table_name="tos_versions",
        schema="school",
    )
    op.drop_table("tos_versions", schema="school")
