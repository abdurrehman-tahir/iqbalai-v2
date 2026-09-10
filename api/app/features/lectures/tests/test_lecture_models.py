"""T-113 — Lecture data-model tests (offline: metadata + JSONB shapes).

Acceptance (M-09 T-113):
1. All four tables exist with constraints in both schemas.
2. lecture_type enum (main/mini) + nullable parent_lecture_id (Flow 7-ready).
3. source_metadata_jsonb on paragraphs holds provenance.
4. Independent lectures have null grade_subject_offering_id + null school_id.
5. Soft-delete + versioning columns present.
"""

from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest
from pydantic import ValidationError
from sqlalchemy import CheckConstraint, Table, UniqueConstraint
from sqlalchemy import Enum as SAEnum

from app.db.base import Base, SoftDeleteMixin
from app.features.lectures import models
from app.features.lectures.models import (
    IndependentLecture,
    IndependentLectureDraft,
    IndependentLectureParagraph,
    IndependentLectureVersion,
    LectureStatus,
    LectureTenantType,
    LectureType,
    SchoolLecture,
    SchoolLectureDraft,
    SchoolLectureParagraph,
    SchoolLectureVersion,
)
from app.features.lectures.schemas import (
    ParagraphSourceMetadata,
    SourceTier,
    WizardState,
)

_SCHOOL_MIGRATION = (
    Path(__file__).resolve().parents[4] / "alembic" / "versions" / "school" / "0051_lectures.py"
)
_INDEPENDENT_MIGRATION = (
    Path(__file__).resolve().parents[4]
    / "alembic"
    / "versions"
    / "independent"
    / "0012_lectures.py"
)

_FOUR_TABLES = ("lectures", "lecture_versions", "lecture_drafts", "lecture_paragraphs")


def test_all_four_tables_registered_in_both_schemas() -> None:
    """Acceptance #1 — four tables in school + independent."""
    for schema in ("school", "independent"):
        for name in _FOUR_TABLES:
            key = f"{schema}.{name}"
            assert key in Base.metadata.tables, f"missing table {key}"


def test_lecture_type_enum_main_mini() -> None:
    """Acceptance #2 — lecture_type enum is main | mini."""
    assert list(LectureType) == [LectureType.MAIN, LectureType.MINI]
    col = SchoolLecture.__table__.columns["lecture_type"]
    assert isinstance(col.type, SAEnum)
    assert set(col.type.enums) == {"main", "mini"}
    assert SchoolLecture.__table__.columns["parent_lecture_id"].nullable is True


def test_mini_requires_parent_check() -> None:
    """Acceptance #2 — CHECK: mini lectures must reference a parent."""
    tables = (
        cast(Table, SchoolLecture.__table__),
        cast(Table, IndependentLecture.__table__),
    )
    for table in tables:
        names = {c.name for c in table.constraints if isinstance(c, CheckConstraint)}
        assert "lectures_mini_requires_parent_check" in names


def test_source_metadata_jsonb_provenance_roundtrip() -> None:
    """Acceptance #3 — source_metadata_jsonb holds provenance tiers."""
    meta = ParagraphSourceMetadata(
        tier=SourceTier.REFERENCE,
        book_name="Halliday Resnick",
        chunk_id="chunk-1",
    )
    raw = meta.to_jsonb()
    restored = ParagraphSourceMetadata.from_jsonb(raw)
    assert restored.tier == SourceTier.REFERENCE
    assert restored.book_name == "Halliday Resnick"

    para = SchoolLectureParagraph(
        lecture_version_id="ver-1",
        ordinal=0,
        text="Newton's third law.",
        source_metadata_jsonb=raw,
    )
    assert para.source_metadata_jsonb["tier"] == "reference"
    assert "source_metadata_jsonb" in SchoolLectureParagraph.__table__.columns
    assert "source_metadata_jsonb" in IndependentLectureParagraph.__table__.columns


def test_source_metadata_rejects_unknown_tier() -> None:
    with pytest.raises(ValidationError):
        ParagraphSourceMetadata(tier="hallucinated")  # type: ignore[arg-type]


def test_independent_school_and_offering_always_null() -> None:
    """Acceptance #4 — independent lectures force null school_id + offering_id."""
    row = IndependentLecture(
        teacher_user_id="ind-teacher-1",
        title="Optics",
        topic="Reflection",
        school_id="should-be-cleared",
        grade_subject_offering_id="should-be-cleared",
    )
    assert row.school_id is None
    assert row.grade_subject_offering_id is None
    assert row.tenant_type == LectureTenantType.INDEPENDENT

    table = cast(Table, IndependentLecture.__table__)
    check_names = {c.name for c in table.constraints if isinstance(c, CheckConstraint)}
    assert "lectures_independent_school_null_check" in check_names
    assert "lectures_independent_offering_null_check" in check_names

    # No cross-schema FKs on school_id / offering_id.
    assert table.c.school_id.foreign_keys == set()
    assert table.c.grade_subject_offering_id.foreign_keys == set()


def test_soft_delete_and_versioning_columns() -> None:
    """Acceptance #5 — soft-delete on lectures/drafts; versioning on versions."""
    assert issubclass(SchoolLecture, SoftDeleteMixin)
    assert issubclass(IndependentLecture, SoftDeleteMixin)
    assert issubclass(SchoolLectureDraft, SoftDeleteMixin)
    assert issubclass(IndependentLectureDraft, SoftDeleteMixin)
    assert "deleted_at" in SchoolLecture.__table__.columns
    assert "deleted_at" in IndependentLecture.__table__.columns

    # Versions are append-only — no SoftDeleteMixin.
    assert not issubclass(SchoolLectureVersion, SoftDeleteMixin)
    assert not issubclass(IndependentLectureVersion, SoftDeleteMixin)
    assert "deleted_at" not in SchoolLectureVersion.__table__.columns
    assert "current_version_id" in SchoolLecture.__table__.columns
    assert "scores_jsonb" in SchoolLectureVersion.__table__.columns
    assert SchoolLectureVersion.__table__.columns["scores_jsonb"].nullable is True


def test_version_unique_per_lecture() -> None:
    tables = (
        cast(Table, SchoolLectureVersion.__table__),
        cast(Table, IndependentLectureVersion.__table__),
    )
    for table in tables:
        uniques = [c for c in table.constraints if isinstance(c, UniqueConstraint)]
        cols = {frozenset(c.columns.keys()) for c in uniques}
        assert frozenset({"lecture_id", "version"}) in cols


def test_school_lecture_defaults() -> None:
    row = SchoolLecture(
        school_id="sch-1",
        teacher_user_id="t-1",
        title="Forces",
        topic="Newton's Laws",
    )
    assert row.lecture_type == LectureType.MAIN
    assert row.status == LectureStatus.DRAFT
    assert row.tenant_type == LectureTenantType.SCHOOL
    assert row.parent_lecture_id is None
    assert row.current_version_id is None


def test_wizard_state_jsonb_shape() -> None:
    state = WizardState(step=2, data={"topic": "Optics"})
    raw = state.to_jsonb()
    draft = SchoolLectureDraft(teacher_user_id="t-1", wizard_state_jsonb=raw)
    assert draft.wizard_state_jsonb["step"] == 2


def test_migrations_define_both_schemas() -> None:
    school_text = _SCHOOL_MIGRATION.read_text(encoding="utf-8")
    indie_text = _INDEPENDENT_MIGRATION.read_text(encoding="utf-8")
    for table in _FOUR_TABLES:
        assert table in school_text
        assert table in indie_text
    assert "lectures_lecture_type_enum" in school_text
    assert "lectures_lecture_type_enum" in indie_text
    assert "source_metadata_jsonb" in school_text
    assert "lectures_independent_school_null_check" in indie_text
    assert "lectures_current_version_id_fk" in school_text
    assert models.SchoolLecture.__tablename__ == "lectures"
