"""T-198 — mini-lecture generation reuse + limits + event."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.features.lectures.models import LectureType
from app.features.next_day_review.classification import ClassifiedCluster
from app.features.next_day_review.mini_generation import (
    MINI_COST_CEILING_USD,
    MINI_LECTURE_GENERATED,
    enforce_mini_limits,
    estimate_mini_cost_usd,
    generate_mini_for_cluster,
    word_count,
)
from app.infrastructure.llm.prompts.mini_lecture_gen_v1 import (
    PROMPT_VERSION,
    WORD_TARGET_MAX,
    WORD_TARGET_MIN,
    LectureGenerateInput,
    render,
)


def test_mini_prompt_targets_800_1200_words() -> None:
    call = render(LectureGenerateInput(topic="Correct force misconception"))
    assert call.version == PROMPT_VERSION
    assert str(WORD_TARGET_MIN) in call.system
    assert str(WORD_TARGET_MAX) in call.system
    assert "web" not in call.system.lower() or "Do NOT invent web" in call.system


def test_cost_ceiling_enforced() -> None:
    assert MINI_COST_CEILING_USD == 0.50
    ok, _ = enforce_mini_limits("word " * 1000)
    assert ok is True
    # Pathological length fails hard.
    ok, reason = enforce_mini_limits("word " * 5000)
    assert ok is False
    assert "word_count" in reason or "cost" in reason


def test_estimate_under_ceiling_for_target_band() -> None:
    assert estimate_mini_cost_usd(WORD_TARGET_MAX) < MINI_COST_CEILING_USD
    assert word_count("one two three") == 3


def _qualifying_cluster() -> ClassifiedCluster:
    return ClassifiedCluster(
        cluster_ref="lec-1|p1|c1#c0",
        bucket_key="lec-1|p1|c1",
        items=[
            {
                "question_id": "q1",
                "user_id": "u1",
                "lecture_id": "parent-1",
                "question_text": "Why is force mass times acceleration backwards?",
            }
        ],
        unique_student_count=3,
        roster_size=20,
        freq_score=1.0,
        frequency_qualifies=True,
        criticality=8,
        criticality_qualifies=True,
        qualifies_for_mini_lecture=True,
        gso_id="gso-1",
    )


@pytest.mark.asyncio
async def test_generate_mini_sets_type_parent_disables_web_publishes_event() -> None:
    """Acceptance #1–#3, #5."""
    parent = MagicMock()
    parent.id = "parent-1"
    parent.school_id = "sch-1"
    parent.grade_subject_offering_id = "gso-1"
    parent.teacher_user_id = "teacher-1"

    mini = MagicMock()
    mini.id = "mini-1"
    mini.current_version_id = "ver-1"

    version = MagicMock()
    version.body = "word " * 900

    session = MagicMock()
    session.get = AsyncMock(side_effect=[parent, mini, version])
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()

    created: dict[str, Any] = {}

    def _capture_add(obj: Any) -> None:
        created["lecture"] = obj
        # Simulate ORM assigning id on flush.
        if getattr(obj, "id", None) is None or True:
            object.__setattr__(obj, "id", "mini-1")

    session.add.side_effect = _capture_add

    with (
        patch(
            "app.features.next_day_review.mini_generation._resolve_library_ids",
            new=AsyncMock(return_value=("curr-1", ["ref-1"])),
        ),
        patch(
            "app.features.next_day_review.mini_generation.run_lecture_generation",
            new=AsyncMock(return_value="ver-1"),
        ) as gen,
        patch(
            "app.features.next_day_review.mini_generation.publish_lecture_event",
            new=AsyncMock(),
        ) as pub,
    ):
        result = await generate_mini_for_cluster(
            session, school_id="sch-1", cluster=_qualifying_cluster()
        )

    assert result is not None
    assert result["status"] == "generated"
    assert result["parent_lecture_id"] == "parent-1"
    lecture = created["lecture"]
    assert lecture.lecture_type == LectureType.MINI
    assert lecture.parent_lecture_id == "parent-1"
    assert gen.await_args is not None
    assert gen.await_args.kwargs["allow_web_fallback"] is False
    pub.assert_awaited()
    assert pub.await_args is not None
    assert pub.await_args.kwargs["event_type"] == MINI_LECTURE_GENERATED


@pytest.mark.asyncio
async def test_non_qualifying_cluster_skipped() -> None:
    cluster = _qualifying_cluster()
    cluster.qualifies_for_mini_lecture = False
    session = MagicMock()
    result = await generate_mini_for_cluster(session, school_id="sch-1", cluster=cluster)
    assert result is None
