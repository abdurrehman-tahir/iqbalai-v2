"""T-195 — next-day review data-model tests (offline: metadata + category).

Acceptance (M-16 T-195):
1. All four tables exist (school schema), tenant-tagged
2. lecture_reviews.acted_actions is an array (multiple actions per review)
3. lecture_reviews links to parent lecture via lecture_id
4. teacher_ai_memory accepts reflective_response_pattern (no migration)
5. DLQ table ready for cluster-level failures
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
from typing import cast

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKeyConstraint, String, Table, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB

from app.db.base import Base
from app.features.next_day_review import models as review_models
from app.features.next_day_review.categories import REFLECTIVE_RESPONSE_PATTERN
from app.features.next_day_review.models import (
    LectureReview,
    LectureReviewStatus,
    ReviewClassificationFailure,
    ReviewReply,
    SkippedCluster,
)
from app.features.teacher_coaching.models import SchoolTeacherAiMemory, TeacherResponseType

_SCHOOL_MIGRATION = (
    Path(__file__).resolve().parents[4]
    / "alembic"
    / "versions"
    / "school"
    / "0080_next_day_review.py"
)

_FOUR_TABLES = (
    "lecture_reviews",
    "review_replies",
    "skipped_clusters",
    "review_classification_failures",
)


def test_all_four_tables_school_schema_only() -> None:
    """Acceptance #1 — school schema only (independent excluded, §3.16)."""
    assert review_models is not None
    for name in _FOUR_TABLES:
        assert f"school.{name}" in Base.metadata.tables, f"missing school.{name}"
        assert f"independent.{name}" not in Base.metadata.tables


def test_migration_file_exists_and_revises_0079() -> None:
    assert _SCHOOL_MIGRATION.is_file()
    text = _SCHOOL_MIGRATION.read_text(encoding="utf-8")
    assert 'revision: str = "school_0080"' in text
    assert 'down_revision: str = "school_0079"' in text
    for name in _FOUR_TABLES:
        assert name in text


def test_acted_actions_is_jsonb_array() -> None:
    """Acceptance #2."""
    col = cast(Table, LectureReview.__table__).columns["acted_actions"]
    assert isinstance(col.type, JSONB)
    row = LectureReview(
        lecture_id="lec-1",
        gso_id="gso-1",
        review_date=date(2026, 10, 15),
        acted_actions=["publish_mini", "reply_cluster"],
    )
    assert row.acted_actions == ["publish_mini", "reply_cluster"]
    assert row.pending_action is True
    assert row.status == LectureReviewStatus.PENDING


def test_lecture_reviews_links_to_parent_lecture() -> None:
    """Acceptance #3."""
    table = cast(Table, LectureReview.__table__)
    assert "lecture_id" in table.columns
    fks = [c for c in table.constraints if isinstance(c, ForeignKeyConstraint)]
    # lecture_id and mini_lecture_id both FK to lectures — find the parent one.
    parent_fk = next(fk for fk in fks if set(fk.column_keys) == {"lecture_id"})
    assert parent_fk.ondelete == "CASCADE"
    referred = list(parent_fk.elements)[0].target_fullname
    assert referred is not None
    assert "lectures" in str(referred)


def test_reflective_response_pattern_category_accepted_without_migration() -> None:
    """Acceptance #4 — category is String(50); constant fits and constructs."""
    assert REFLECTIVE_RESPONSE_PATTERN == "reflective_response_pattern"
    assert len(REFLECTIVE_RESPONSE_PATTERN) <= 50

    col = cast(Table, SchoolTeacherAiMemory.__table__).columns["category"]
    assert not isinstance(col.type, SAEnum)
    assert cast(String, col.type).length == 50

    row = SchoolTeacherAiMemory(
        teacher_user_id="t-1",
        category=REFLECTIVE_RESPONSE_PATTERN,
        weakness_type="prefers_concrete_analogies",
        last_suggestion="Teacher answered reflective prompt with concrete-analogy preference.",
    )
    assert row.category == REFLECTIVE_RESPONSE_PATTERN
    assert row.teacher_response == TeacherResponseType.NONE


def test_dlq_table_ready_for_cluster_failures() -> None:
    """Acceptance #5."""
    table = cast(Table, ReviewClassificationFailure.__table__)
    for col in ("school_id", "gso_id", "cluster_ref", "error", "failed_at"):
        assert col in table.columns
        assert table.columns[col].nullable is False

    row = ReviewClassificationFailure(
        school_id="sch-1",
        gso_id="gso-1",
        cluster_ref="cluster-abc",
        error="LLM timeout",
        failed_at=datetime.now(timezone.utc),
    )
    assert row.cluster_ref == "cluster-abc"


def test_status_enum_stable_three_values() -> None:
    assert list(LectureReviewStatus) == [
        LectureReviewStatus.PENDING,
        LectureReviewStatus.COMPLETED,
        LectureReviewStatus.DISMISSED,
    ]
    col = LectureReview.__table__.columns["status"]
    assert isinstance(col.type, SAEnum)
    assert set(col.type.enums) == {"pending", "completed", "dismissed"}


def test_review_reply_and_skipped_cluster_cascade_from_review() -> None:
    for model_cls, fk_col in (
        (ReviewReply, "review_id"),
        (SkippedCluster, "review_id"),
    ):
        table = cast(Table, model_cls.__table__)
        fks = [c for c in table.constraints if isinstance(c, ForeignKeyConstraint)]
        review_fk = next(fk for fk in fks if set(fk.column_keys) == {fk_col})
        assert review_fk.ondelete == "CASCADE"


def test_skipped_clusters_unique_per_review_cluster() -> None:
    table = cast(Table, SkippedCluster.__table__)
    uniques = [c for c in table.constraints if isinstance(c, UniqueConstraint)]
    cols = {frozenset(c.columns.keys()) for c in uniques}
    assert frozenset({"review_id", "cluster_ref"}) in cols


def test_lecture_reviews_unique_per_lecture_gso_date() -> None:
    table = cast(Table, LectureReview.__table__)
    uniques = [c for c in table.constraints if isinstance(c, UniqueConstraint)]
    cols = {frozenset(c.columns.keys()) for c in uniques}
    assert frozenset({"lecture_id", "gso_id", "review_date"}) in cols
