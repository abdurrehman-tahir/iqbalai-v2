"""Add independent_personal_content table (T-074).

Revision ID: independent_0005
Revises: independent_0004
Create Date: 2026-06-22

Purpose: Private reference pool for independent users.
Risk: low
Reversible: yes
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision: str = "independent_0005"
down_revision: str = "independent_0004"
branch_labels: tuple[()] = ()
depends_on: str | None = None


def upgrade() -> None:
    op.execute(
        "CREATE TYPE independent.personalcontenttype AS ENUM ('curriculum', 'reference')"
    )
    op.execute(
        "CREATE TYPE independent.personalcontentstatus AS ENUM "
        "('pending', 'ingesting', 'available', 'failed')"
    )
    op.execute(
        "CREATE TYPE independent.personalstructuredparsingstatus AS ENUM "
        "('pending', 'complete', 'failed', 'not_applicable')"
    )

    op.create_table(
        "independent_personal_content",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("independent.users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "content_type",
            sa.Enum(
                "curriculum",
                "reference",
                name="personalcontenttype",
                schema="independent",
                create_type=False,
            ),
            nullable=False,
            server_default="reference",
        ),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("file_key", sa.String(500), nullable=False),
        sa.Column("file_sha256", sa.String(64), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "ingesting",
                "available",
                "failed",
                name="personalcontentstatus",
                schema="independent",
                create_type=False,
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "structured_parsing_status",
            sa.Enum(
                "pending",
                "complete",
                "failed",
                "not_applicable",
                name="personalstructuredparsingstatus",
                schema="independent",
                create_type=False,
            ),
            nullable=True,
        ),
        sa.Column("topic_tree_jsonb", JSONB, nullable=True),
        sa.Column("vector_collection", sa.String(150), nullable=False),
        sa.Column("ingestion_error", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        schema="independent",
    )
    op.create_index(
        "ix_independent_personal_content_user_id",
        "independent_personal_content",
        ["user_id"],
        schema="independent",
    )
    op.create_index(
        "ix_independent_personal_content_file_sha256",
        "independent_personal_content",
        ["file_sha256"],
        schema="independent",
    )
    op.create_index(
        "ix_independent_personal_content_deleted_at",
        "independent_personal_content",
        ["deleted_at"],
        schema="independent",
    )
    op.create_index(
        "independent_personal_content_user_sha256_uq",
        "independent_personal_content",
        ["user_id", "file_sha256"],
        unique=True,
        schema="independent",
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "independent_personal_content_user_sha256_uq",
        table_name="independent_personal_content",
        schema="independent",
    )
    op.drop_index(
        "ix_independent_personal_content_deleted_at",
        table_name="independent_personal_content",
        schema="independent",
    )
    op.drop_index(
        "ix_independent_personal_content_file_sha256",
        table_name="independent_personal_content",
        schema="independent",
    )
    op.drop_index(
        "ix_independent_personal_content_user_id",
        table_name="independent_personal_content",
        schema="independent",
    )
    op.drop_table("independent_personal_content", schema="independent")
    op.execute("DROP TYPE IF EXISTS independent.personalstructuredparsingstatus")
    op.execute("DROP TYPE IF EXISTS independent.personalcontentstatus")
    op.execute("DROP TYPE IF EXISTS independent.personalcontenttype")
