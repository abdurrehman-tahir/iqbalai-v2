"""Cognitive DNA seed model tests — T-102."""

from __future__ import annotations

import inspect
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.features.cognitive_dna import models as dna_models
from app.features.cognitive_dna.models import (
    CognitiveDnaSource,
    CognitiveDnaTenantType,
    IndependentCognitiveDna,
    SchoolCognitiveDna,
)
from app.features.cognitive_dna.repository import CognitiveDnaRepository
from app.features.cognitive_dna.schemas import FocusArea, FocusAreasList, TopicConfidenceMap


def test_tables_live_in_separate_schemas() -> None:
    assert SchoolCognitiveDna.__table__.schema == "school"
    assert IndependentCognitiveDna.__table__.schema == "independent"
    assert SchoolCognitiveDna.__tablename__ == "cognitive_dna"
    assert IndependentCognitiveDna.__tablename__ == "cognitive_dna"


def test_source_enum_starts_with_diagnostic_only() -> None:
    assert list(CognitiveDnaSource) == [CognitiveDnaSource.DIAGNOSTIC]
    assert CognitiveDnaSource.DIAGNOSTIC.value == "diagnostic"


def test_provisional_todo_comment_present() -> None:
    source = inspect.getsource(dna_models)
    assert "TODO(Flow-9/M-18)" in source
    assert "provisional" in source.lower() or "MINIMAL seed" in source


def test_jsonb_topic_confidence_round_trip() -> None:
    blob = TopicConfidenceMap(scores={"newton": 0.4, "optics": 0.8})
    raw = blob.to_jsonb()
    restored = TopicConfidenceMap.from_jsonb(raw)
    assert restored.scores == {"newton": 0.4, "optics": 0.8}


def test_jsonb_topic_confidence_rejects_out_of_range() -> None:
    with pytest.raises(ValidationError):
        TopicConfidenceMap(scores={"bad": 1.5})


def test_jsonb_focus_areas_round_trip() -> None:
    blob = FocusAreasList(areas=[FocusArea(topic="Newton's Laws", reason="Missed force diagrams")])
    raw = blob.to_jsonb()
    restored = FocusAreasList.from_jsonb(raw)
    assert restored.areas[0].topic == "Newton's Laws"


def test_school_row_defaults_and_jsonb() -> None:
    now = datetime.now(timezone.utc)
    row = SchoolCognitiveDna(
        student_user_id="stu-1",
        subject_id="subj-1",
        topic_confidence_jsonb=TopicConfidenceMap(scores={"a": 0.5}).to_jsonb(),
        focus_areas_jsonb=FocusAreasList(areas=[FocusArea(topic="a", reason="focus")]).to_jsonb(),
        last_updated_at=now,
    )
    assert row.tenant_type == CognitiveDnaTenantType.SCHOOL
    assert row.source == CognitiveDnaSource.DIAGNOSTIC
    assert row.topic_confidence_jsonb == {"a": 0.5}
    assert isinstance(row.focus_areas_jsonb, list)


def test_independent_row_defaults() -> None:
    now = datetime.now(timezone.utc)
    row = IndependentCognitiveDna(
        student_user_id="ind-1",
        framework_id="fw-1",
        last_updated_at=now,
    )
    assert row.tenant_type == CognitiveDnaTenantType.INDEPENDENT
    assert row.subject_id is None


def test_repository_picks_model_by_tenant() -> None:
    school_repo = CognitiveDnaRepository(session=None, tenant_type="school")  # type: ignore[arg-type]
    indie_repo = CognitiveDnaRepository(session=None, tenant_type="independent")  # type: ignore[arg-type]
    assert school_repo._model is SchoolCognitiveDna
    assert indie_repo._model is IndependentCognitiveDna


def test_no_cross_schema_fk_on_independent_framework() -> None:
    """Independent framework_id must not FK into school (ARCH §4.21)."""
    # Import registers independent.users on Base.metadata for FK resolution.
    from app.features.independent_users.models import IndependentUser  # noqa: F401

    fk_targets: set[str] = set()
    for col in IndependentCognitiveDna.__table__.columns:
        for fk in col.foreign_keys:
            table = fk.column.table
            schema = table.schema or ""
            fk_targets.add(f"{schema}.{table.name}")
    assert fk_targets == {"independent.users"}
    assert IndependentCognitiveDna.__table__.c.framework_id.foreign_keys == set()
