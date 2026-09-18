"""School migration: FK indexes on lecture_plagiarism_flags.

Revision ID: school_0064
Revises: school_0063
Create Date: 2026-09-15

Purpose: ARCH §4 requires an index on every foreign key. The T-129/T-135
lecture_plagiarism_flags table shipped indexes on lecture_version_id,
teacher_user_id, and status but omitted matched_lecture_version_id and
reviewed_by_user_id — caught by the repo-wide `test_every_foreign_key_has_
ondelete_and_index` model-metadata test. Model columns now declare
index=True (via __table_args__); this migration adds the matching DB
indexes.
Risk: low — additive indexes only.
Reversible: yes
"""

from __future__ import annotations

from alembic import op

revision: str = "school_0064"
down_revision: str = "school_0063"
branch_labels: tuple[()] = ()
depends_on: str | None = None

_SCHEMA = "school"


def upgrade() -> None:
    op.create_index(
        "ix_lecture_plagiarism_flags_matched_lecture_version_id",
        "lecture_plagiarism_flags",
        ["matched_lecture_version_id"],
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_lecture_plagiarism_flags_reviewed_by_user_id",
        "lecture_plagiarism_flags",
        ["reviewed_by_user_id"],
        schema=_SCHEMA,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_lecture_plagiarism_flags_reviewed_by_user_id",
        table_name="lecture_plagiarism_flags",
        schema=_SCHEMA,
    )
    op.drop_index(
        "ix_lecture_plagiarism_flags_matched_lecture_version_id",
        table_name="lecture_plagiarism_flags",
        schema=_SCHEMA,
    )
