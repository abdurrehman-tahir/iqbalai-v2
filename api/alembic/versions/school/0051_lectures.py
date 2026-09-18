"""School migration: lecture tables (T-113).

Revision ID: school_0051
Revises: school_0050
Create Date: 2026-07-30

Purpose: lectures / lecture_versions / lecture_drafts / lecture_paragraphs (school).
Risk: low — additive tables only; Flow-7 mini parent_lecture_id reserved.
Reversible: yes
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "school_0051"
down_revision: str = "school_0050"
branch_labels: tuple[()] = ()
depends_on: str | None = None

_SCHEMA = "school"

_STATUS_VALUES = (
    "draft",
    "generating",
    "generated_v1",
    "ready_for_edit",
    "ready_for_publish",
    "published",
    "archived",
    "failed",
    "timed_out",
)


def _create_enum_if_missing(qualified_name: str, values_sql: str) -> None:
    # Idempotent CREATE TYPE — never emit CREATE TYPE via sa.Enum create_table
    # (AUDIT_LOG [migration-enum-create]).
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
            "WHERE table_schema = :schema AND table_name = 'lectures'"
        ),
        {"schema": _SCHEMA},
    ).scalar():
        return

    _create_enum_if_missing(
        f"{_SCHEMA}.lectures_lecture_type_enum",
        "'main', 'mini'",
    )
    status_list = ", ".join(f"'{v}'" for v in _STATUS_VALUES)
    _create_enum_if_missing(f"{_SCHEMA}.lectures_status_enum", status_list)
    _create_enum_if_missing(
        f"{_SCHEMA}.lectures_tenant_type_enum",
        "'school', 'independent'",
    )

    lecture_type = postgresql.ENUM(
        "main",
        "mini",
        name="lectures_lecture_type_enum",
        schema=_SCHEMA,
        create_type=False,
    )
    status = postgresql.ENUM(
        *_STATUS_VALUES,
        name="lectures_status_enum",
        schema=_SCHEMA,
        create_type=False,
    )
    tenant_type = postgresql.ENUM(
        "school",
        "independent",
        name="lectures_tenant_type_enum",
        schema=_SCHEMA,
        create_type=False,
    )

    op.create_table(
        "lectures",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_type", tenant_type, nullable=False),
        sa.Column(
            "school_id",
            sa.String(36),
            sa.ForeignKey(f"{_SCHEMA}.schools.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "grade_subject_offering_id",
            sa.String(36),
            sa.ForeignKey(f"{_SCHEMA}.grade_subject_offerings.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "teacher_user_id",
            sa.String(36),
            sa.ForeignKey(f"{_SCHEMA}.users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("topic", sa.String(500), nullable=False),
        sa.Column("lecture_type", lecture_type, nullable=False, server_default="main"),
        sa.Column("parent_lecture_id", sa.String(36), nullable=True),
        sa.Column("status", status, nullable=False, server_default="draft"),
        sa.Column("current_version_id", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "lecture_type <> 'mini' OR parent_lecture_id IS NOT NULL",
            name="lectures_mini_requires_parent_check",
        ),
        sa.ForeignKeyConstraint(
            ["parent_lecture_id"],
            [f"{_SCHEMA}.lectures.id"],
            name="lectures_parent_lecture_id_fk",
            ondelete="SET NULL",
        ),
        schema=_SCHEMA,
    )
    op.create_index("ix_lectures_school_id", "lectures", ["school_id"], schema=_SCHEMA)
    op.create_index(
        "ix_lectures_grade_subject_offering_id",
        "lectures",
        ["grade_subject_offering_id"],
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_lectures_teacher_user_id",
        "lectures",
        ["teacher_user_id"],
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_lectures_parent_lecture_id",
        "lectures",
        ["parent_lecture_id"],
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_lectures_current_version_id",
        "lectures",
        ["current_version_id"],
        schema=_SCHEMA,
    )
    op.create_index("ix_lectures_deleted_at", "lectures", ["deleted_at"], schema=_SCHEMA)

    op.create_table(
        "lecture_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "lecture_id",
            sa.String(36),
            sa.ForeignKey(f"{_SCHEMA}.lectures.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("scores_jsonb", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "lecture_id",
            "version",
            name="lecture_versions_lecture_version_uq",
        ),
        sa.CheckConstraint("version >= 1", name="lecture_versions_version_positive_check"),
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_lecture_versions_lecture_id",
        "lecture_versions",
        ["lecture_id"],
        schema=_SCHEMA,
    )

    # Circular FK: lectures.current_version_id → lecture_versions.id
    op.create_foreign_key(
        "lectures_current_version_id_fk",
        "lectures",
        "lecture_versions",
        ["current_version_id"],
        ["id"],
        source_schema=_SCHEMA,
        referent_schema=_SCHEMA,
        ondelete="RESTRICT",
    )

    op.create_table(
        "lecture_paragraphs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "lecture_version_id",
            sa.String(36),
            sa.ForeignKey(f"{_SCHEMA}.lecture_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column(
            "source_metadata_jsonb",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text('\'{"tier": "ai_knowledge"}\'::jsonb'),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "lecture_version_id",
            "ordinal",
            name="lecture_paragraphs_version_ordinal_uq",
        ),
        sa.CheckConstraint("ordinal >= 0", name="lecture_paragraphs_ordinal_nonneg_check"),
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_lecture_paragraphs_lecture_version_id",
        "lecture_paragraphs",
        ["lecture_version_id"],
        schema=_SCHEMA,
    )

    op.create_table(
        "lecture_drafts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "teacher_user_id",
            sa.String(36),
            sa.ForeignKey(f"{_SCHEMA}.users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "wizard_state_jsonb",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text('\'{"step": 1, "data": {}}\'::jsonb'),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_lecture_drafts_teacher_user_id",
        "lecture_drafts",
        ["teacher_user_id"],
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_lecture_drafts_deleted_at",
        "lecture_drafts",
        ["deleted_at"],
        schema=_SCHEMA,
    )
    op.execute(
        f"""
        CREATE UNIQUE INDEX lecture_drafts_teacher_user_id_uq
        ON {_SCHEMA}.lecture_drafts (teacher_user_id)
        WHERE deleted_at IS NULL
        """
    )


def downgrade() -> None:
    op.execute(f"DROP INDEX IF EXISTS {_SCHEMA}.lecture_drafts_teacher_user_id_uq")
    op.drop_index("ix_lecture_drafts_deleted_at", table_name="lecture_drafts", schema=_SCHEMA)
    op.drop_index(
        "ix_lecture_drafts_teacher_user_id",
        table_name="lecture_drafts",
        schema=_SCHEMA,
    )
    op.drop_table("lecture_drafts", schema=_SCHEMA)

    op.drop_index(
        "ix_lecture_paragraphs_lecture_version_id",
        table_name="lecture_paragraphs",
        schema=_SCHEMA,
    )
    op.drop_table("lecture_paragraphs", schema=_SCHEMA)

    op.drop_constraint(
        "lectures_current_version_id_fk",
        "lectures",
        schema=_SCHEMA,
        type_="foreignkey",
    )
    op.drop_index(
        "ix_lecture_versions_lecture_id",
        table_name="lecture_versions",
        schema=_SCHEMA,
    )
    op.drop_table("lecture_versions", schema=_SCHEMA)

    op.drop_index("ix_lectures_deleted_at", table_name="lectures", schema=_SCHEMA)
    op.drop_index("ix_lectures_current_version_id", table_name="lectures", schema=_SCHEMA)
    op.drop_index("ix_lectures_parent_lecture_id", table_name="lectures", schema=_SCHEMA)
    op.drop_index("ix_lectures_teacher_user_id", table_name="lectures", schema=_SCHEMA)
    op.drop_index(
        "ix_lectures_grade_subject_offering_id",
        table_name="lectures",
        schema=_SCHEMA,
    )
    op.drop_index("ix_lectures_school_id", table_name="lectures", schema=_SCHEMA)
    op.drop_table("lectures", schema=_SCHEMA)

    op.execute(f"DROP TYPE IF EXISTS {_SCHEMA}.lectures_tenant_type_enum")
    op.execute(f"DROP TYPE IF EXISTS {_SCHEMA}.lectures_status_enum")
    op.execute(f"DROP TYPE IF EXISTS {_SCHEMA}.lectures_lecture_type_enum")
