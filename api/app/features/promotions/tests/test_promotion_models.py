"""T-250 — grade_promotion_requests model + migration shape tests."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import cast

from sqlalchemy import Index, Table

from app.db.base import Base
from app.features.promotions.models import (
    GradePromotionRequest,
    GradePromotionRequestStatus,
)
from app.features.promotions.schemas import (
    GradePromotionRequestCreate,
    GradePromotionRequestRead,
)

_VERSIONS = Path(__file__).resolve().parents[4] / "alembic" / "versions" / "school"
TABLE: Table = cast(Table, GradePromotionRequest.__table__)


def test_table_identity_school_schema() -> None:
    assert GradePromotionRequest.__tablename__ == "grade_promotion_requests"
    assert TABLE.schema == "school"
    assert "school.grade_promotion_requests" in Base.metadata.tables


def test_status_enum_matches_arch_6_21() -> None:
    assert {s.value for s in GradePromotionRequestStatus} == {
        "pending_approval",
        "approved",
        "rejected",
        "executing",
        "executed",
        "expired",
        "failed",
    }


def test_model_round_trip_defaults() -> None:
    now = datetime.now(timezone.utc)
    row = GradePromotionRequest(
        school_id="school-1",
        initiating_grade_id="grade-9",
        target_academic_session="2026-2027",
        target_grade_name="Grade 10",
        initiated_by_coordinator_id="coord-1",
        exclusion_list_jsonb=["student-a", "student-b"],
        requested_at=now,
    )
    assert len(row.id) == 36
    assert row.status is GradePromotionRequestStatus.PENDING_APPROVAL
    assert row.retry_count == 0
    assert row.target_grade_id is None
    assert row.exclusion_list_jsonb == ["student-a", "student-b"]
    assert row.deleted_at is None

    read = GradePromotionRequestRead.model_validate(row)
    assert read.status is GradePromotionRequestStatus.PENDING_APPROVAL
    assert read.exclusion_list_jsonb == ["student-a", "student-b"]
    assert read.retry_count == 0


def test_create_schema_accepts_exclusion_list() -> None:
    body = GradePromotionRequestCreate(
        target_academic_session="2026-2027",
        target_grade_name="Grade 10",
        exclusion_list=["s1"],
    )
    assert body.exclusion_list == ["s1"]


def test_fk_ondelete_choices() -> None:
    fks = {fk.parent.name: fk.ondelete for fk in TABLE.foreign_keys}
    assert fks["school_id"] == "RESTRICT"
    assert fks["initiating_grade_id"] == "RESTRICT"
    assert fks["target_grade_id"] == "SET NULL"
    assert fks["initiated_by_coordinator_id"] == "RESTRICT"
    assert fks["approved_by_user_id"] == "SET NULL"


def test_pending_per_grade_partial_unique() -> None:
    indexes = {str(idx.name): idx for idx in TABLE.indexes if isinstance(idx, Index) and idx.name}
    uq = indexes["grade_promotion_requests_pending_grade_uq"]
    assert uq.unique is True
    assert tuple(col.name for col in uq.columns) == ("initiating_grade_id",)
    where = str(uq.dialect_options["postgresql"]["where"])
    assert "pending_approval" in where
    assert "deleted_at IS NULL" in where


def test_migration_file_covers_enum_and_table() -> None:
    text = (_VERSIONS / "0080_grade_promotion_requests.py").read_text(encoding="utf-8")
    assert "school_0080" in text
    assert "school_0079" in text
    assert "grade_promotion_request_status" in text
    assert "grade_promotion_requests" in text
    assert "pending_approval" in text
    assert "exclusion_list_jsonb" in text
    assert "grade_promotion_requests_pending_grade_uq" in text
    assert "CREATE TYPE" in text
    assert "create_type=False" in text
