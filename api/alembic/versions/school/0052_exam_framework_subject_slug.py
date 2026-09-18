"""Add exam_frameworks.subject_slug — T-120 (lecture exam-framework overlay).

Controlled-vocabulary subject match (e.g. "physics") so lecture generation can
find frameworks relevant to a lecture's Subject without a FK: `subjects` rows
are school-scoped (one row per school), but a framework applies across every
school, so no single `subjects.id` could represent it. Matched at generation
time against each school's free-text `Subject.name` via normalization
(app/features/lectures/exam_overlay.py), not stored on `subjects`.

`independent.exam_frameworks` (independent_0007) is a read-only view over this
table — extended via CREATE OR REPLACE with the new column appended at the end
(Postgres allows appending to a view's column list without dropping it; only
changing/reordering existing columns requires a drop, per school_0046).

Revision ID: school_0052
Revises: school_0051
Create Date: 2026-07-31

Purpose: exam_frameworks.subject_slug column + index; independent view extended.
Risk: low — additive column with a temporary backfill default, then default dropped.
Reversible: yes
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "school_0052"
down_revision: str = "school_0051"
branch_labels: tuple[()] = ()
depends_on: tuple[str, ...] | None = ("independent_0007",)

# Backfill value for any pre-existing rows — Platform Admin must set a real slug
# on next edit; the API's ExamFrameworkUpdate schema requires a real value going
# forward (this default exists only to satisfy the NOT NULL constraint on ADD COLUMN).
_BACKFILL_UNASSIGNED = "unassigned"

_VIEW_WITH_SLUG = """
    CREATE OR REPLACE VIEW independent.exam_frameworks AS
    SELECT
        id,
        name,
        exam_target,
        region,
        target_grade_range,
        language,
        status,
        created_by,
        created_at,
        updated_at,
        deleted_at,
        subject_slug
    FROM school.exam_frameworks
    WHERE status = 'published' AND deleted_at IS NULL
"""

_VIEW_WITHOUT_SLUG = """
    CREATE OR REPLACE VIEW independent.exam_frameworks AS
    SELECT
        id,
        name,
        exam_target,
        region,
        target_grade_range,
        language,
        status,
        created_by,
        created_at,
        updated_at,
        deleted_at
    FROM school.exam_frameworks
    WHERE status = 'published' AND deleted_at IS NULL
"""


def upgrade() -> None:
    op.add_column(
        "exam_frameworks",
        sa.Column(
            "subject_slug", sa.String(50), nullable=False, server_default=_BACKFILL_UNASSIGNED
        ),
        schema="school",
    )
    op.alter_column("exam_frameworks", "subject_slug", server_default=None, schema="school")
    op.create_index(
        "ix_exam_frameworks_subject_slug",
        "exam_frameworks",
        ["subject_slug"],
        schema="school",
    )
    op.execute(_VIEW_WITH_SLUG)


def downgrade() -> None:
    # Postgres allows CREATE OR REPLACE to APPEND columns to a view (used in
    # upgrade()) but refuses to DROP one that way ("cannot drop columns from
    # view") — removing subject_slug needs an actual drop + recreate.
    op.execute("DROP VIEW IF EXISTS independent.exam_frameworks")
    op.execute(_VIEW_WITHOUT_SLUG.replace("CREATE OR REPLACE VIEW", "CREATE VIEW"))
    op.drop_index("ix_exam_frameworks_subject_slug", table_name="exam_frameworks", schema="school")
    op.drop_column("exam_frameworks", "subject_slug", schema="school")
