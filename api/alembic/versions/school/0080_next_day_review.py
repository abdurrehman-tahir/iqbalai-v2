"""School migration: next-day review tables (T-195, Flow 7 §3.1 / §3.6 / §3.8).

Revision ID: school_0080
Revises: school_0079
Create Date: 2026-10-15

Purpose: lecture_reviews + review_replies + skipped_clusters +
review_classification_failures (DLQ). School schema only — mini-lectures /
reviews are excluded from the independent tenant (ARCH §3.16).
``teacher_ai_memory.category`` already accepts ``reflective_response_pattern``
as a plain String(50); no column change required (M-10 T-129).
Risk: low — additive tables + one new enum.
Reversible: yes

Hand-authored to match LectureReview / ReviewReply / SkippedCluster /
ReviewClassificationFailure (model-first; autogenerate pruned of unrelated drift).
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "school_0080"
down_revision: str = "school_0079"
branch_labels: tuple[()] = ()
depends_on: str | None = None

_SCHEMA = "school"
_STATUS_VALUES = ("pending", "completed", "dismissed")


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
    status_list = ", ".join(f"'{v}'" for v in _STATUS_VALUES)
    _create_enum_if_missing(f"{_SCHEMA}.lecture_reviews_status_enum", status_list)

    status_enum = postgresql.ENUM(
        *_STATUS_VALUES,
        name="lecture_reviews_status_enum",
        schema=_SCHEMA,
        create_type=False,
    )

    op.create_table(
        "lecture_reviews",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("lecture_id", sa.String(length=36), nullable=False),
        sa.Column("gso_id", sa.String(length=36), nullable=False),
        sa.Column("review_date", sa.Date(), nullable=False),
        sa.Column("ai_summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("reflective_prompt", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "status",
            status_enum,
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "pending_action",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("dismissed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "acted_actions",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("mini_lecture_id", sa.String(length=36), nullable=True),
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
        sa.ForeignKeyConstraint(["lecture_id"], ["school.lectures.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["gso_id"],
            ["school.grade_subject_offerings.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["mini_lecture_id"],
            ["school.lectures.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "lecture_id",
            "gso_id",
            "review_date",
            name="lecture_reviews_lecture_gso_date_uq",
        ),
        schema=_SCHEMA,
    )
    for name, cols in (
        ("ix_lecture_reviews_lecture_id", ["lecture_id"]),
        ("ix_lecture_reviews_gso_id", ["gso_id"]),
        ("ix_lecture_reviews_mini_lecture_id", ["mini_lecture_id"]),
        ("ix_lecture_reviews_review_date", ["review_date"]),
        ("ix_lecture_reviews_status", ["status"]),
    ):
        op.create_index(name, "lecture_reviews", cols, schema=_SCHEMA)

    op.create_table(
        "review_replies",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("review_id", sa.String(length=36), nullable=False),
        sa.Column("cluster_id", sa.String(length=100), nullable=False),
        sa.Column("student_user_id", sa.String(length=36), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["review_id"],
            ["school.lecture_reviews.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["student_user_id"],
            ["school.users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        schema=_SCHEMA,
    )
    op.create_index("ix_review_replies_review_id", "review_replies", ["review_id"], schema=_SCHEMA)
    op.create_index(
        "ix_review_replies_student_user_id",
        "review_replies",
        ["student_user_id"],
        schema=_SCHEMA,
    )

    op.create_table(
        "skipped_clusters",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("review_id", sa.String(length=36), nullable=False),
        sa.Column("cluster_ref", sa.String(length=200), nullable=False),
        sa.Column("skipped_at", sa.DateTime(timezone=True), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["review_id"],
            ["school.lecture_reviews.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "review_id",
            "cluster_ref",
            name="skipped_clusters_review_cluster_uq",
        ),
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_skipped_clusters_review_id",
        "skipped_clusters",
        ["review_id"],
        schema=_SCHEMA,
    )

    op.create_table(
        "review_classification_failures",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("school_id", sa.String(length=36), nullable=False),
        sa.Column("gso_id", sa.String(length=36), nullable=False),
        sa.Column("cluster_ref", sa.String(length=200), nullable=False),
        sa.Column("error", sa.Text(), nullable=False),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["school_id"],
            ["school.schools.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["gso_id"],
            ["school.grade_subject_offerings.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_review_classification_failures_school_id",
        "review_classification_failures",
        ["school_id"],
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_review_classification_failures_gso_id",
        "review_classification_failures",
        ["gso_id"],
        schema=_SCHEMA,
    )


def downgrade() -> None:
    for name in (
        "ix_review_classification_failures_gso_id",
        "ix_review_classification_failures_school_id",
    ):
        op.drop_index(name, table_name="review_classification_failures", schema=_SCHEMA)
    op.drop_table("review_classification_failures", schema=_SCHEMA)

    op.drop_index("ix_skipped_clusters_review_id", table_name="skipped_clusters", schema=_SCHEMA)
    op.drop_table("skipped_clusters", schema=_SCHEMA)

    for name in ("ix_review_replies_student_user_id", "ix_review_replies_review_id"):
        op.drop_index(name, table_name="review_replies", schema=_SCHEMA)
    op.drop_table("review_replies", schema=_SCHEMA)

    for name in (
        "ix_lecture_reviews_status",
        "ix_lecture_reviews_review_date",
        "ix_lecture_reviews_mini_lecture_id",
        "ix_lecture_reviews_gso_id",
        "ix_lecture_reviews_lecture_id",
    ):
        op.drop_index(name, table_name="lecture_reviews", schema=_SCHEMA)
    op.drop_table("lecture_reviews", schema=_SCHEMA)

    op.execute(f"DROP TYPE IF EXISTS {_SCHEMA}.lecture_reviews_status_enum")
