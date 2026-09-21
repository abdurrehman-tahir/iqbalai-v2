"""School migration: lecture TTS audio cache (T-153).

Revision ID: school_0067
Revises: school_0066
Create Date: 2026-09-21

Purpose: lecture_audio_caches — MinIO pointer + sentence alignment per
lecture+language for student karaoke voice mode (Flow 6 §3.2 / #54).
Risk: low — additive table + enum only.
Reversible: yes
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "school_0067"
down_revision: str = "school_0066"
branch_labels: tuple[()] = ()
depends_on: str | None = None

_SCHEMA = "school"
_STATUS_VALUES = ("pending", "ready", "failed", "invalidated")


def _create_enum_if_missing(qualified_name: str, values_sql: str) -> None:
    op.execute(
        f"""
        DO $$ BEGIN
            CREATE TYPE {qualified_name} AS ENUM ({values_sql});
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$;
        """
    )


def upgrade() -> None:
    conn = op.get_bind()
    if conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = :schema AND table_name = 'lecture_audio_caches'"
        ),
        {"schema": _SCHEMA},
    ).scalar():
        return

    _create_enum_if_missing(
        f"{_SCHEMA}.lecture_audio_caches_status_enum",
        ", ".join(f"'{v}'" for v in _STATUS_VALUES),
    )
    status_enum = postgresql.ENUM(
        *_STATUS_VALUES,
        name="lecture_audio_caches_status_enum",
        schema=_SCHEMA,
        create_type=False,
    )

    op.create_table(
        "lecture_audio_caches",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "lecture_id",
            sa.String(36),
            sa.ForeignKey(f"{_SCHEMA}.lectures.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "lecture_version_id",
            sa.String(36),
            sa.ForeignKey(f"{_SCHEMA}.lecture_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("language", sa.String(8), nullable=False),
        sa.Column("status", status_enum, nullable=False, server_default="pending"),
        sa.Column("audio_storage_key", sa.String(512), nullable=True),
        sa.Column("content_type", sa.String(64), nullable=True),
        sa.Column("byte_size", sa.Integer(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("alignment_jsonb", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "lecture_id",
            "language",
            name="lecture_audio_caches_lecture_language_uq",
        ),
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_lecture_audio_caches_lecture_id",
        "lecture_audio_caches",
        ["lecture_id"],
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_lecture_audio_caches_lecture_version_id",
        "lecture_audio_caches",
        ["lecture_version_id"],
        schema=_SCHEMA,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_lecture_audio_caches_lecture_version_id",
        table_name="lecture_audio_caches",
        schema=_SCHEMA,
    )
    op.drop_index(
        "ix_lecture_audio_caches_lecture_id",
        table_name="lecture_audio_caches",
        schema=_SCHEMA,
    )
    op.drop_table("lecture_audio_caches", schema=_SCHEMA)
    op.execute(f"DROP TYPE IF EXISTS {_SCHEMA}.lecture_audio_caches_status_enum")
