"""T-120 — Exam framework overlay (Flow 4 v3 §3.5.4): additive exam-readiness context."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.features.exam_frameworks.models import FrameworkStatus, StudyPlanStatus
from app.features.lectures.exam_overlay import get_exam_framework_overlay, normalize_subject_slug


class _Rows:
    """Fake SQLAlchemy Result for plain-column selects (`.all()` -> list of tuples)."""

    def __init__(self, values: list[Any]) -> None:
        self._values = values

    def all(self) -> list[tuple[Any]]:
        return [(v,) for v in self._values]


class _Scalars:
    def __init__(self, objs: list[Any]) -> None:
        self._objs = objs

    def all(self) -> list[Any]:
        return self._objs

    def first(self) -> Any:
        return self._objs[0] if self._objs else None


class _ScalarResult:
    """Fake SQLAlchemy Result for ORM-object selects (`.scalars().all()/.first()`)."""

    def __init__(self, objs: list[Any]) -> None:
        self._objs = objs

    def scalars(self) -> _Scalars:
        return _Scalars(self._objs)


def _framework(**overrides: Any) -> MagicMock:
    fw = MagicMock()
    fw.id = overrides.get("id", "fw-1")
    fw.name = overrides.get("name", "Matric Punjab — Physics")
    fw.subject_slug = overrides.get("subject_slug", "physics")
    fw.status = overrides.get("status", FrameworkStatus.PUBLISHED)
    fw.target_grade_range = overrides.get("target_grade_range", [9, 10])
    fw.deleted_at = overrides.get("deleted_at", None)
    return fw


def _plan(content_jsonb: dict[str, Any]) -> MagicMock:
    plan = MagicMock()
    plan.status = StudyPlanStatus.APPROVED
    plan.content_jsonb = content_jsonb
    return plan


_CONTENT = {
    "version": 1,
    "framework_name": "Matric Punjab — Physics",
    "region": "Punjab",
    "target_grade_range": [9, 10],
    "sources_cited": [],
    "generated_at": "2026-01-01T00:00:00Z",
    "topics": [
        {
            "topic_name": "Newton's Laws",
            "priority_weight": 0.9,
            "exam_frequency": "every_year",
            "recommended_hours": 4,
        },
        {
            "topic_name": "Optics",
            "priority_weight": 0.4,
            "exam_frequency": "alternate_years",
            "recommended_hours": 2,
        },
    ],
    "weekly_pacing": [],
    "exam_strategy": {
        "time_allocation": "Spend 20 minutes on numericals.",
        "scoring_strategy": "Show all working for partial marks.",
        "common_mistakes": [],
    },
    "copyright_note": "",
}


class TestNormalizeSubjectSlug:
    def test_simple_name(self) -> None:
        assert normalize_subject_slug("Physics") == "physics"

    def test_multi_word_name(self) -> None:
        assert normalize_subject_slug("General Science") == "general-science"

    def test_strips_punctuation_and_extra_space(self) -> None:
        assert normalize_subject_slug("  Physics (Advanced) ") == "physics-advanced"


@pytest.mark.asyncio
async def test_no_overlay_when_no_students_enrolled() -> None:
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[_Rows([])])

    result = await get_exam_framework_overlay(session, grade_id="g-1", subject_name="Physics")

    assert result is None
    assert session.execute.await_count == 1


@pytest.mark.asyncio
async def test_no_overlay_when_no_active_selections() -> None:
    session = AsyncMock()
    session.execute = AsyncMock(
        side_effect=[
            _Rows(["stu-1", "stu-2"]),
            _Rows([]),
        ]
    )

    result = await get_exam_framework_overlay(session, grade_id="g-1", subject_name="Physics")

    assert result is None


@pytest.mark.asyncio
async def test_no_overlay_when_no_framework_matches_subject_and_grade() -> None:
    session = AsyncMock()
    session.get = AsyncMock(return_value=MagicMock(level_ordinal=9))
    session.execute = AsyncMock(
        side_effect=[
            _Rows(["stu-1"]),
            _Rows(["fw-1"]),
            _ScalarResult([]),  # no PUBLISHED framework matched subject_slug
        ]
    )

    result = await get_exam_framework_overlay(session, grade_id="g-1", subject_name="Physics")

    assert result is None


@pytest.mark.asyncio
async def test_no_overlay_when_framework_does_not_cover_grade() -> None:
    session = AsyncMock()
    session.get = AsyncMock(return_value=MagicMock(level_ordinal=11))  # outside [9, 10]
    session.execute = AsyncMock(
        side_effect=[
            _Rows(["stu-1"]),
            _Rows(["fw-1"]),
            _ScalarResult([_framework(target_grade_range=[9, 10])]),
        ]
    )

    result = await get_exam_framework_overlay(session, grade_id="g-1", subject_name="Physics")

    assert result is None


@pytest.mark.asyncio
async def test_no_overlay_when_no_approved_study_plan() -> None:
    session = AsyncMock()
    session.get = AsyncMock(return_value=MagicMock(level_ordinal=9))
    session.execute = AsyncMock(
        side_effect=[
            _Rows(["stu-1"]),
            _Rows(["fw-1"]),
            _ScalarResult([_framework()]),
            _ScalarResult([]),  # no APPROVED plan yet
        ]
    )

    result = await get_exam_framework_overlay(session, grade_id="g-1", subject_name="Physics")

    assert result is None


@pytest.mark.asyncio
async def test_relevant_framework_returns_strategy_and_top_priority_topics() -> None:
    session = AsyncMock()
    session.get = AsyncMock(return_value=MagicMock(level_ordinal=9))
    session.execute = AsyncMock(
        side_effect=[
            _Rows(["stu-1"]),
            _Rows(["fw-1"]),
            _ScalarResult([_framework()]),
            _ScalarResult([_plan(_CONTENT)]),
        ]
    )

    result = await get_exam_framework_overlay(session, grade_id="g-1", subject_name="Physics")

    assert result is not None
    assert result.framework_name == "Matric Punjab — Physics"
    assert "20 minutes" in result.exam_strategy_summary
    assert "Show all working" in result.exam_strategy_summary
    # Ranked by priority_weight descending.
    assert result.priority_topics[0].startswith("Newton's Laws")
    assert result.priority_topics[1].startswith("Optics")
