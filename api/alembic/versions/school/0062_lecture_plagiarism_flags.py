"""School migration: lecture_plagiarism_flags table (T-129, Flow 5 §3.7 #33).

Revision ID: school_0062
Revises: school_0061
Create Date: 2026-09-11

Purpose: admin-only queue raised when the global originality check's
max_similarity exceeds 0.85 (T-135). School-tenant only — the global
cross-teacher index never includes independent-tenant lectures. Matched
version/teacher are stored for Platform-Admin triage but must never be
exposed to any other role (ARCH §7.15 privacy rule).
Risk: low — additive table only.
Reversible: yes
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "school_0062"
down_revision: str = "school_0061"
branch_labels: tuple[()] = ()
depends_on: str | None = None

_SCHEMA = "school"
_STATUS_VALUES = ("open", "reviewed", "dismissed")


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
    status_list = ", ".join(f"'{v}'" for v in _STATUS_VALUES)
    _create_enum_if_missing(f"{_SCHEMA}.lecture_plagiarism_flags_status_enum", status_list)

    status_enum = postgresql.ENUM(
        *_STATUS_VALUES,
        name="lecture_plagiarism_flags_status_enum",
        schema=_SCHEMA,
        create_type=False,
    )

    op.create_table(
        "lecture_plagiarism_flags",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "lecture_version_id",
            sa.String(36),
            sa.ForeignKey(f"{_SCHEMA}.lecture_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "teacher_user_id",
            sa.String(36),
            sa.ForeignKey(f"{_SCHEMA}.users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "matched_lecture_version_id",
            sa.String(36),
            sa.ForeignKey(f"{_SCHEMA}.lecture_versions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("similarity_score", sa.Numeric(4, 3), nullable=False),
        sa.Column("status", status_enum, nullable=False, server_default="open"),
        sa.Column(
            "reviewed_by_user_id",
            sa.String(36),
            sa.ForeignKey(f"{_SCHEMA}.users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "similarity_score >= 0 AND similarity_score <= 1",
            name="lecture_plagiarism_flags_similarity_range_check",
        ),
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_lecture_plagiarism_flags_lecture_version_id",
        "lecture_plagiarism_flags",
        ["lecture_version_id"],
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_lecture_plagiarism_flags_teacher_user_id",
        "lecture_plagiarism_flags",
        ["teacher_user_id"],
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_lecture_plagiarism_flags_status",
        "lecture_plagiarism_flags",
        ["status"],
        schema=_SCHEMA,
    )


def downgrade() -> None:
    op.drop_table("lecture_plagiarism_flags", schema=_SCHEMA)
    op.execute(f"DROP TYPE IF EXISTS {_SCHEMA}.lecture_plagiarism_flags_status_enum")
