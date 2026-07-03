"""Add independent_personal_content table (T-074).

Revision ID: independent_0005
Revises: independent_0004
Create Date: 2026-06-22

Purpose: Private reference pool for independent users.
Risk: low
Reversible: yes
"""

from __future__ import annotations

from sqlalchemy import inspect, text

from alembic import op

revision: str = "independent_0005"
down_revision: str = "independent_0004"
branch_labels: tuple[()] = ()
depends_on: str | None = None


def _ensure_enum(schema: str, name: str, values: str) -> None:
    op.execute(
        f"""
        DO $$ BEGIN
            CREATE TYPE {schema}.{name} AS ENUM ({values});
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$;
        """
    )


def upgrade() -> None:
    _ensure_enum("independent", "personalcontenttype", "'curriculum', 'reference'")
    _ensure_enum(
        "independent",
        "personalcontentstatus",
        "'pending', 'ingesting', 'available', 'failed'",
    )
    _ensure_enum(
        "independent",
        "personalstructuredparsingstatus",
        "'pending', 'complete', 'failed', 'not_applicable'",
    )

    bind = op.get_bind()
    if inspect(bind).has_table("independent_personal_content", schema="independent"):
        return

    op.execute(
        text(
            """
            CREATE TABLE independent.independent_personal_content (
                id VARCHAR(36) PRIMARY KEY,
                user_id VARCHAR(36) NOT NULL REFERENCES independent.users (id) ON DELETE RESTRICT,
                content_type independent.personalcontenttype NOT NULL DEFAULT 'reference',
                title VARCHAR(500) NOT NULL,
                file_key VARCHAR(500) NOT NULL,
                file_sha256 VARCHAR(64) NOT NULL,
                status independent.personalcontentstatus NOT NULL DEFAULT 'pending',
                structured_parsing_status independent.personalstructuredparsingstatus,
                topic_tree_jsonb JSONB,
                vector_collection VARCHAR(150) NOT NULL,
                ingestion_error TEXT,
                created_at TIMESTAMPTZ NOT NULL,
                updated_at TIMESTAMPTZ NOT NULL,
                deleted_at TIMESTAMPTZ
            )
            """
        )
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
    op.execute(
        """
        CREATE UNIQUE INDEX independent_personal_content_user_sha256_uq
        ON independent.independent_personal_content (user_id, file_sha256)
        WHERE deleted_at IS NULL
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS independent.independent_personal_content_user_sha256_uq")
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
