"""Cross-schema read-only views for platform-shared tables (T-073).

Revision ID: independent_0004
Revises: independent_0003
Create Date: 2026-06-22

Purpose: Expose school.platform_reference_books to independent schema queries.
Risk: low
Reversible: yes
"""

from __future__ import annotations

from alembic import op

revision: str = "independent_0004"
down_revision: str = "independent_0003"
branch_labels: tuple[()] = ()
depends_on: str | None = None


def upgrade() -> None:
    op.execute("""
        CREATE VIEW independent.platform_reference_books AS
        SELECT
            id,
            upload_id,
            title,
            content_type,
            subject_tag,
            grade_range_min,
            grade_range_max,
            language,
            sha256,
            status,
            qdrant_collection,
            chunk_count,
            created_at,
            updated_at,
            deleted_at
        FROM school.platform_reference_books
        WHERE deleted_at IS NULL
    """)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS independent.platform_reference_books")
