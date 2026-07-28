"""Independent migration: provisional cognitive_dna seed table (T-102).

Revision ID: independent_0008
Revises: independent_0007
Create Date: 2026-07-28

Purpose: Minimal Cognitive DNA store in independent schema (tenant isolation).
Risk: low
Reversible: yes
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "independent_0008"
down_revision: str = "independent_0007"
branch_labels: tuple[()] = ()
depends_on: str | None = None


def upgrade() -> None:
    conn = op.get_bind()
    if conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = 'independent' AND table_name = 'cognitive_dna'"
        )
    ).scalar():
        return

    op.execute("CREATE TYPE independent.cognitive_dna_source_enum AS ENUM ('diagnostic')")
    op.execute(
        "CREATE TYPE independent.cognitive_dna_tenant_type_enum AS ENUM ('school', 'independent')"
    )

    source = postgresql.ENUM(
        "diagnostic",
        name="cognitive_dna_source_enum",
        schema="independent",
        create_type=False,
    )
    tenant_type = postgresql.ENUM(
        "school",
        "independent",
        name="cognitive_dna_tenant_type_enum",
        schema="independent",
        create_type=False,
    )

    op.create_table(
        "cognitive_dna",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_type", tenant_type, nullable=False),
        sa.Column(
            "student_user_id",
            sa.String(36),
            sa.ForeignKey("independent.users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("subject_id", sa.String(36), nullable=True),
        sa.Column("framework_id", sa.String(36), nullable=True),
        sa.Column(
            "topic_confidence_jsonb",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "focus_areas_jsonb",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("source", source, nullable=False),
        sa.Column("last_updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        schema="independent",
    )
    op.create_index(
        "ix_cognitive_dna_student_user_id",
        "cognitive_dna",
        ["student_user_id"],
        schema="independent",
    )
    op.create_index(
        "ix_cognitive_dna_subject_id",
        "cognitive_dna",
        ["subject_id"],
        schema="independent",
    )
    op.create_index(
        "ix_cognitive_dna_framework_id",
        "cognitive_dna",
        ["framework_id"],
        schema="independent",
    )
    op.create_index(
        "ix_cognitive_dna_deleted_at",
        "cognitive_dna",
        ["deleted_at"],
        schema="independent",
    )


def downgrade() -> None:
    op.drop_index("ix_cognitive_dna_deleted_at", table_name="cognitive_dna", schema="independent")
    op.drop_index("ix_cognitive_dna_framework_id", table_name="cognitive_dna", schema="independent")
    op.drop_index("ix_cognitive_dna_subject_id", table_name="cognitive_dna", schema="independent")
    op.drop_index(
        "ix_cognitive_dna_student_user_id",
        table_name="cognitive_dna",
        schema="independent",
    )
    op.drop_table("cognitive_dna", schema="independent")
    op.execute("DROP TYPE IF EXISTS independent.cognitive_dna_tenant_type_enum")
    op.execute("DROP TYPE IF EXISTS independent.cognitive_dna_source_enum")
