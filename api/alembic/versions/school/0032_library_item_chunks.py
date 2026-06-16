"""library_item_chunks metadata table — T-056.

Revision ID: school_0032
Revises: school_0031
Create Date: 2026-06-16

Purpose: Persist chunk metadata linked to library_items for school-tier RAG ingestion.
Risk: low
Reversible: yes
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "school_0032"
down_revision: str = "school_0031"
branch_labels: tuple[()] = ()
depends_on: str | None = None


def upgrade() -> None:
    conn = op.get_bind()
    if conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = 'school' AND table_name = 'library_item_chunks'"
        )
    ).scalar():
        return

    op.create_table(
        "library_item_chunks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("library_item_id", sa.String(36), nullable=False),
        sa.Column("school_id", sa.String(36), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("qdrant_point_id", sa.String(36), nullable=False),
        sa.Column("chunk_text", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now() AT TIME ZONE 'UTC'"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now() AT TIME ZONE 'UTC'"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["library_item_id"], ["school.library_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["school_id"], ["school.schools.id"], ondelete="RESTRICT"),
        schema="school",
    )
    op.create_index(
        "ix_library_item_chunks_library_item_id",
        "library_item_chunks",
        ["library_item_id"],
        schema="school",
    )
    op.create_index(
        "ix_library_item_chunks_school_id",
        "library_item_chunks",
        ["school_id"],
        schema="school",
    )
    op.create_index(
        "library_item_chunks_item_index_uq",
        "library_item_chunks",
        ["library_item_id", "chunk_index"],
        unique=True,
        schema="school",
    )

    op.execute("ALTER TABLE school.library_item_chunks ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE school.library_item_chunks FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY library_item_chunks_isolation ON school.library_item_chunks
        USING (
            current_setting('app.current_role', true) = 'platform_admin'
            OR school_id = current_setting('app.current_school_id', true)
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS library_item_chunks_isolation ON school.library_item_chunks")
    op.drop_index("library_item_chunks_item_index_uq", table_name="library_item_chunks", schema="school")
    op.drop_index("ix_library_item_chunks_school_id", table_name="library_item_chunks", schema="school")
    op.drop_index(
        "ix_library_item_chunks_library_item_id",
        table_name="library_item_chunks",
        schema="school",
    )
    op.drop_table("library_item_chunks", schema="school")
