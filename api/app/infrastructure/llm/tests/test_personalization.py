"""T-108 — DNA personalization read-hook tests."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock

import pytest

from app.features.cognitive_dna.models import (
    CognitiveDnaSource,
    CognitiveDnaTenantType,
    IndependentCognitiveDna,
    SchoolCognitiveDna,
)
from app.features.cognitive_dna.schemas import FocusAreasList
from app.infrastructure.llm.personalization import (
    format_focus_areas_prompt_block,
    resolve_dna_focus_areas,
)


class _FakeDnaRepo:
    row: Any = None

    def __init__(self, session: Any, tenant_type: str) -> None:
        self.tenant_type = tenant_type

    async def get_for_scope(
        self,
        *,
        student_user_id: str,
        subject_id: str | None,
        framework_id: str | None,
    ) -> Any:
        return self.row


@pytest.fixture(autouse=True)
def _patch_repo(monkeypatch: pytest.MonkeyPatch) -> None:
    _FakeDnaRepo.row = None
    monkeypatch.setattr(
        "app.infrastructure.llm.personalization.CognitiveDnaRepository",
        _FakeDnaRepo,
    )


@pytest.mark.asyncio
async def test_resolve_empty_when_no_dna() -> None:
    ctx = await resolve_dna_focus_areas(
        AsyncMock(),
        student_user_id="stu-1",
        tenant_type="school",
        subject_id="subj-1",
    )
    assert ctx.focus_areas == []
    assert ctx.has_focus_areas is False
    assert ctx.tenant_type == "school"


@pytest.mark.asyncio
async def test_resolve_school_focus_areas_from_seed() -> None:
    _FakeDnaRepo.row = SchoolCognitiveDna(
        student_user_id="stu-1",
        subject_id="subj-physics",
        framework_id=None,
        topic_confidence_jsonb={},
        focus_areas_jsonb=[
            {"topic": "Optics", "suggestion": "Spend more time on Optics."},
            {"topic": "Friction", "reason": "Review friction examples."},
        ],
        source=CognitiveDnaSource.DIAGNOSTIC,
        last_updated_at=datetime.now(timezone.utc),
        tenant_type=CognitiveDnaTenantType.SCHOOL,
    )
    ctx = await resolve_dna_focus_areas(
        AsyncMock(),
        student_user_id="stu-1",
        tenant_type="school",
        subject_id="subj-physics",
    )
    assert len(ctx.focus_areas) == 2
    assert ctx.focus_areas[0].topic == "Optics"
    assert "Optics" in ctx.focus_areas[0].reason
    assert ctx.focus_areas[1].reason == "Review friction examples."
    block = format_focus_areas_prompt_block(ctx.focus_areas)
    assert "coaching" in block.lower()
    assert "Optics" in block
    assert "%" not in block
    assert "never treat as grades" in block.lower()


@pytest.mark.asyncio
async def test_resolve_independent_scope() -> None:
    _FakeDnaRepo.row = IndependentCognitiveDna(
        student_user_id="ind-1",
        subject_id=None,
        framework_id="fw-1",
        topic_confidence_jsonb={},
        focus_areas_jsonb=[{"topic": "Algebra", "suggestion": "Practice algebra."}],
        source=CognitiveDnaSource.DIAGNOSTIC,
        last_updated_at=datetime.now(timezone.utc),
        tenant_type=CognitiveDnaTenantType.INDEPENDENT,
    )
    ctx = await resolve_dna_focus_areas(
        AsyncMock(),
        student_user_id="ind-1",
        tenant_type="independent",
        framework_id="fw-1",
    )
    assert ctx.tenant_type == "independent"
    assert ctx.framework_id == "fw-1"
    assert ctx.focus_areas[0].topic == "Algebra"


def test_focus_areas_list_accepts_suggestion_key() -> None:
    parsed = FocusAreasList.from_jsonb(
        [{"topic": "Newton", "suggestion": "Spend more time on Newton's Laws."}]
    )
    assert parsed.areas[0].reason.startswith("Spend more time")


def test_format_empty() -> None:
    assert format_focus_areas_prompt_block([]) == ""
