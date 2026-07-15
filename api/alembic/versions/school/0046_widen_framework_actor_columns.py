"""Widen exam-framework Authentik-sub actor columns from VARCHAR(36) to VARCHAR(255).

Same defect class as school_0014: the routers pass the Authentik JWT `sub` through as
`actor_id`, and subs can be 64-char hashes, so a VARCHAR(36) actor column raises
StringDataRightTruncationError on write. M-07's new framework tables reintroduced it.

Affected columns:
  school.exam_frameworks.created_by      (QA E01 — create framework 500s)
  school.framework_study_plans.approved_by  (same bug, latent: approve plan would 500)

Both columns are projected by the independent-schema read-only views (independent_0007),
and Postgres refuses to alter a column type a view depends on ("cannot alter type of a
column used by a view or rule"), so the views are dropped and recreated verbatim around
the ALTERs. `depends_on` pins independent_0007 so that on a fresh database the views
already exist when this runs — otherwise this would recreate them and independent_0007
would later fail on CREATE VIEW.

Revision ID: school_0046
Revises: school_0045
Create Date: 2026-07-14

Purpose: Fix exam-framework create/approve 500 when storing the JWT sub.
Risk: low
Reversible: yes
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "school_0046"
down_revision: str = "school_0045"
branch_labels: tuple[()] = ()
depends_on: tuple[str, ...] | None = ("independent_0007",)

# Verbatim from independent_0007 — kept identical so the drop/recreate is a no-op for
# consumers. If those view definitions change, this must be updated in lockstep.
_CREATE_FRAMEWORKS_VIEW = """
    CREATE VIEW independent.exam_frameworks AS
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

_CREATE_STUDY_PLANS_VIEW = """
    CREATE VIEW independent.framework_study_plans AS
    SELECT
        id,
        framework_id,
        version,
        content_jsonb,
        sources_cited_jsonb,
        generated_at,
        approved_by,
        approved_at,
        status,
        created_at,
        updated_at
    FROM school.framework_study_plans
    WHERE status = 'approved'
"""


def upgrade() -> None:
    op.execute("DROP VIEW IF EXISTS independent.framework_study_plans")
    op.execute("DROP VIEW IF EXISTS independent.exam_frameworks")

    op.alter_column(
        "exam_frameworks",
        "created_by",
        existing_type=sa.String(36),
        type_=sa.String(255),
        existing_nullable=False,
        schema="school",
    )
    op.alter_column(
        "framework_study_plans",
        "approved_by",
        existing_type=sa.String(36),
        type_=sa.String(255),
        existing_nullable=True,
        schema="school",
    )

    op.execute(_CREATE_FRAMEWORKS_VIEW)
    op.execute(_CREATE_STUDY_PLANS_VIEW)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS independent.framework_study_plans")
    op.execute("DROP VIEW IF EXISTS independent.exam_frameworks")

    # Narrowing truncates any stored 64-char sub; rows written since the upgrade would
    # fail this ALTER rather than silently lose data. That is intended.
    op.alter_column(
        "framework_study_plans",
        "approved_by",
        existing_type=sa.String(255),
        type_=sa.String(36),
        existing_nullable=True,
        schema="school",
    )
    op.alter_column(
        "exam_frameworks",
        "created_by",
        existing_type=sa.String(255),
        type_=sa.String(36),
        existing_nullable=False,
        schema="school",
    )

    op.execute(_CREATE_FRAMEWORKS_VIEW)
    op.execute(_CREATE_STUDY_PLANS_VIEW)
