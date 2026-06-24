"""School-tier library_items + library_item_selections — T-054.

Revision ID: school_0030
Revises: school_0029
Create Date: 2026-06-16

Purpose: Content Library data model (school tier) with RLS + sample seed rows.
Risk: low
Reversible: yes
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "school_0030"
down_revision: str = "school_0029"
branch_labels: tuple[()] = ()
depends_on: str | None = None

_DEMO_SCHOOL_ID = "5c000000-0000-4000-8000-000000000001"
_SAMPLE_CURRICULUM_ID = "lib-curriculum-sample-000000000001"
_SAMPLE_REFERENCE_ID = "lib-reference-sample-000000000001"
_SAMPLE_SELECTION_ID = "lib-selection-sample-000000000001"


def upgrade() -> None:
    conn = op.get_bind()
    if conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = 'school' AND table_name = 'library_items'"
        )
    ).scalar():
        return

    op.create_table(
        "library_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("school_id", sa.String(36), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column(
            "content_type",
            sa.Enum(
                "curriculum", "reference", name="library_items_content_type_enum", schema="school"
            ),
            nullable=False,
        ),
        sa.Column("language", sa.String(10), nullable=False, server_default="en"),
        sa.Column("subject_id", sa.String(36), nullable=True),
        sa.Column("grade_level_ordinal", sa.Integer(), nullable=True),
        sa.Column("storage_key", sa.String(500), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column(
            "ingestion_status",
            sa.Enum(
                "pending",
                "ingesting",
                "available",
                "failed",
                name="library_items_ingestion_status_enum",
                schema="school",
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("topic_tree_jsonb", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_by", sa.String(36), nullable=False),
        sa.Column(
            "visibility",
            sa.Enum(
                "private", "school_public", name="library_items_visibility_enum", schema="school"
            ),
            nullable=False,
            server_default="private",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(now() AT TIME ZONE 'UTC')"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(now() AT TIME ZONE 'UTC')"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["school_id"], ["school.schools.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["subject_id"], ["school.subjects.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["school.users.id"], ondelete="RESTRICT"),
        schema="school",
    )
    op.create_index("ix_library_items_school_id", "library_items", ["school_id"], schema="school")
    op.create_index("ix_library_items_created_by", "library_items", ["created_by"], schema="school")
    op.create_index("ix_library_items_sha256", "library_items", ["sha256"], schema="school")
    op.create_index("ix_library_items_subject_id", "library_items", ["subject_id"], schema="school")
    op.create_index("ix_library_items_deleted_at", "library_items", ["deleted_at"], schema="school")
    op.create_index(
        "library_items_school_sha256_uq",
        "library_items",
        ["school_id", "sha256"],
        unique=True,
        schema="school",
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "library_item_selections",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("library_item_id", sa.String(36), nullable=False),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column(
            "selected_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(now() AT TIME ZONE 'UTC')"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(now() AT TIME ZONE 'UTC')"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(now() AT TIME ZONE 'UTC')"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["library_item_id"], ["school.library_items.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["school.users.id"], ondelete="CASCADE"),
        schema="school",
    )
    op.create_index(
        "ix_library_item_selections_library_item_id",
        "library_item_selections",
        ["library_item_id"],
        schema="school",
    )
    op.create_index(
        "ix_library_item_selections_user_id",
        "library_item_selections",
        ["user_id"],
        schema="school",
    )
    op.create_index(
        "ix_library_item_selections_deleted_at",
        "library_item_selections",
        ["deleted_at"],
        schema="school",
    )
    op.create_index(
        "library_item_selections_item_user_uq",
        "library_item_selections",
        ["library_item_id", "user_id"],
        unique=True,
        schema="school",
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.execute("ALTER TABLE school.library_items ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY library_items_isolation ON school.library_items
        USING (
            current_setting('app.current_role', true) = 'platform_admin'
            OR (
                school_id = current_setting('app.current_school_id', true)
                AND (
                    visibility = 'school_public'
                    OR created_by = current_setting('app.current_user_id', true)
                )
            )
        )
        """
    )

    op.execute("ALTER TABLE school.library_item_selections ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY library_item_selections_isolation ON school.library_item_selections
        USING (
            current_setting('app.current_role', true) = 'platform_admin'
            OR user_id = current_setting('app.current_user_id', true)
        )
        """
    )

    # Sample rows when demo school + coordinator exist (seed_dev / M-02 hierarchy).
    op.execute(
        f"""
        INSERT INTO school.library_items (
            id, school_id, title, content_type, language, grade_level_ordinal,
            storage_key, sha256, ingestion_status, created_by, visibility
        )
        SELECT
            '{_SAMPLE_CURRICULUM_ID}',
            '{_DEMO_SCHOOL_ID}',
            'Sample Punjab Physics Grade 9 Curriculum',
            'curriculum',
            'en',
            9,
            'school-library/demo/curriculum-sample.pdf',
            'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
            'available',
            u.id,
            'school_public'
        FROM school.users u
        WHERE u.authentik_id = 'seed-coordinator'
          AND u.school_id = '{_DEMO_SCHOOL_ID}'
          AND NOT EXISTS (
              SELECT 1 FROM school.library_items li WHERE li.id = '{_SAMPLE_CURRICULUM_ID}'
          )
        """
    )
    op.execute(
        f"""
        INSERT INTO school.library_items (
            id, school_id, title, content_type, language,
            storage_key, sha256, ingestion_status, created_by, visibility
        )
        SELECT
            '{_SAMPLE_REFERENCE_ID}',
            '{_DEMO_SCHOOL_ID}',
            'Sample Reference Book',
            'reference',
            'en',
            'school-library/demo/reference-sample.pdf',
            'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
            'available',
            u.id,
            'private'
        FROM school.users u
        WHERE u.authentik_id = 'seed-teacher'
          AND u.school_id = '{_DEMO_SCHOOL_ID}'
          AND NOT EXISTS (
              SELECT 1 FROM school.library_items li WHERE li.id = '{_SAMPLE_REFERENCE_ID}'
          )
        """
    )
    op.execute(
        f"""
        INSERT INTO school.library_item_selections (id, library_item_id, user_id)
        SELECT
            '{_SAMPLE_SELECTION_ID}',
            '{_SAMPLE_REFERENCE_ID}',
            u.id
        FROM school.users u
        WHERE u.authentik_id = 'seed-teacher'
          AND u.school_id = '{_DEMO_SCHOOL_ID}'
          AND EXISTS (SELECT 1 FROM school.library_items li WHERE li.id = '{_SAMPLE_REFERENCE_ID}')
          AND NOT EXISTS (
              SELECT 1 FROM school.library_item_selections s WHERE s.id = '{_SAMPLE_SELECTION_ID}'
          )
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP POLICY IF EXISTS library_item_selections_isolation ON school.library_item_selections"
    )
    op.execute("DROP POLICY IF EXISTS library_items_isolation ON school.library_items")
    op.drop_index(
        "library_item_selections_item_user_uq",
        table_name="library_item_selections",
        schema="school",
    )
    op.drop_index(
        "ix_library_item_selections_deleted_at",
        table_name="library_item_selections",
        schema="school",
    )
    op.drop_index(
        "ix_library_item_selections_user_id",
        table_name="library_item_selections",
        schema="school",
    )
    op.drop_index(
        "ix_library_item_selections_library_item_id",
        table_name="library_item_selections",
        schema="school",
    )
    op.drop_table("library_item_selections", schema="school")
    op.drop_index("library_items_school_sha256_uq", table_name="library_items", schema="school")
    op.drop_index("ix_library_items_deleted_at", table_name="library_items", schema="school")
    op.drop_index("ix_library_items_subject_id", table_name="library_items", schema="school")
    op.drop_index("ix_library_items_sha256", table_name="library_items", schema="school")
    op.drop_index("ix_library_items_created_by", table_name="library_items", schema="school")
    op.drop_index("ix_library_items_school_id", table_name="library_items", schema="school")
    op.drop_table("library_items", schema="school")
    op.execute("DROP TYPE IF EXISTS school.library_items_visibility_enum")
    op.execute("DROP TYPE IF EXISTS school.library_items_ingestion_status_enum")
    op.execute("DROP TYPE IF EXISTS school.library_items_content_type_enum")
