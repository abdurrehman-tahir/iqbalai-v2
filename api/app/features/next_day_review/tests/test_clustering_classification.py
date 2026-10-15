"""T-197 — cosine clustering + frequency/criticality classification + DLQ."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.features.next_day_review.classification import (
    CRITICALITY_THRESHOLD,
    FREQ_MIN_STUDENTS,
    ClassifiedCluster,
    classify_clusters,
    frequency_qualifies,
)
from app.features.next_day_review.clustering import (
    COSINE_THRESHOLD,
    QuestionCluster,
    cluster_embedded_items,
    cosine_similarity,
)
from app.infrastructure.llm.prompts.next_day_review_criticality_v1 import (
    PROMPT_VERSION,
    TASK_ID,
    CriticalityInput,
    CriticalityOutput,
    render,
)


def test_cosine_threshold_locked_at_080() -> None:
    assert COSINE_THRESHOLD == 0.80


def test_cosine_similarity_basics() -> None:
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)
    assert cosine_similarity([1.0, 0.0], [-1.0, 0.0]) == pytest.approx(-1.0)
    assert cosine_similarity([0.0, 0.0], [1.0, 0.0]) == 0.0


def test_cluster_at_cosine_threshold() -> None:
    """Acceptance #1 — similar vectors merge; orthogonal stays separate."""
    items = [
        {"question_id": "q1", "user_id": "u1", "question_text": "a"},
        {"question_id": "q2", "user_id": "u2", "question_text": "b"},
        {"question_id": "q3", "user_id": "u3", "question_text": "c"},
    ]
    # q1≈q2 (cosine 1.0), q3 orthogonal to both.
    vectors = [[1.0, 0.0], [1.0, 0.0], [0.0, 1.0]]
    clusters = cluster_embedded_items(bucket_key="lec|p|c", items=items, vectors=vectors)
    assert len(clusters) == 2
    sizes = sorted(len(c.items) for c in clusters)
    assert sizes == [1, 2]


def test_frequency_qualifies_absolute_and_roster() -> None:
    """Acceptance #2."""
    ok, _ = frequency_qualifies(FREQ_MIN_STUDENTS, roster_size=100)
    assert ok is True
    ok, _ = frequency_qualifies(2, roster_size=100)
    assert ok is False
    ok, _ = frequency_qualifies(2, roster_size=8)  # 25% of 8 = 2
    assert ok is True
    ok, _ = frequency_qualifies(1, roster_size=8)
    assert ok is False


def test_criticality_prompt_render() -> None:
    call = render(CriticalityInput(question_texts=["Why is force equal?"], target_language="en"))
    assert call.version == PROMPT_VERSION
    assert "Why is force equal?" in call.user
    assert TASK_ID == "next_day_review"


def test_criticality_threshold_locked() -> None:
    """Acceptance #3."""
    assert CRITICALITY_THRESHOLD == 7
    out = CriticalityOutput(criticality=7, rationale="high stakes")
    assert out.criticality >= CRITICALITY_THRESHOLD


def _cluster(
    *,
    ref: str,
    students: list[str],
    lecture_id: str = "lec-1",
) -> QuestionCluster:
    items = [
        {
            "question_id": f"q-{uid}",
            "user_id": uid,
            "lecture_id": lecture_id,
            "question_text": f"question from {uid}",
        }
        for uid in students
    ]
    return QuestionCluster(cluster_ref=ref, bucket_key="lec-1|p1|c1", items=items)


@pytest.mark.asyncio
async def test_classify_flags_qualifying_on_frequency_without_llm() -> None:
    """Acceptance #5 — frequency alone flags mini-lecture; LLM mocked high."""
    cluster = _cluster(ref="c1", students=["u1", "u2", "u3"])

    async def _roster(_session: Any, _lecture_id: str) -> tuple[int, str | None]:
        return 20, "gso-1"

    with (
        patch(
            "app.features.next_day_review.classification._roster_size_for_lecture",
            new=_roster,
        ),
        patch(
            "app.features.next_day_review.classification.score_criticality",
            new=AsyncMock(return_value=CriticalityOutput(criticality=3, rationale="low")),
        ),
    ):
        session = MagicMock()
        session.commit = AsyncMock()
        result = await classify_clusters(session, school_id="sch-1", clusters=[cluster])

    assert len(result.qualifying) == 1
    assert result.qualifying[0].frequency_qualifies is True
    assert result.qualifying[0].criticality_qualifies is False
    assert result.qualifying[0].qualifies_for_mini_lecture is True


@pytest.mark.asyncio
async def test_classify_flags_qualifying_on_criticality_alone() -> None:
    cluster = _cluster(ref="c1", students=["u1"])  # below freq floor

    async def _roster(_session: Any, _lecture_id: str) -> tuple[int, str | None]:
        return 40, "gso-1"

    with (
        patch(
            "app.features.next_day_review.classification._roster_size_for_lecture",
            new=_roster,
        ),
        patch(
            "app.features.next_day_review.classification.score_criticality",
            new=AsyncMock(return_value=CriticalityOutput(criticality=9, rationale="critical")),
        ),
    ):
        session = MagicMock()
        session.commit = AsyncMock()
        result = await classify_clusters(session, school_id="sch-1", clusters=[cluster])

    assert result.qualifying[0].criticality_qualifies is True
    assert result.qualifying[0].frequency_qualifies is False


@pytest.mark.asyncio
async def test_cluster_llm_failure_writes_dlq_and_continues() -> None:
    """Acceptance #4 — DLQ row; batch still returns (freq may still qualify)."""
    cluster_ok = _cluster(ref="c-ok", students=["u1", "u2", "u3"])
    cluster_fail = _cluster(ref="c-fail", students=["u4", "u5", "u6"])

    async def _roster(_session: Any, _lecture_id: str) -> tuple[int, str | None]:
        return 30, "gso-1"

    calls = {"n": 0}

    async def _score(cluster: QuestionCluster) -> CriticalityOutput:
        calls["n"] += 1
        if cluster.cluster_ref == "c-fail":
            raise RuntimeError("LLM timeout")
        return CriticalityOutput(criticality=2, rationale="ok")

    with (
        patch(
            "app.features.next_day_review.classification._roster_size_for_lecture",
            new=_roster,
        ),
        patch(
            "app.features.next_day_review.classification.score_criticality",
            new=_score,
        ),
        patch(
            "app.features.next_day_review.classification.write_dlq",
            new=AsyncMock(),
        ) as dlq,
    ):
        session = MagicMock()
        session.commit = AsyncMock()
        result = await classify_clusters(
            session, school_id="sch-1", clusters=[cluster_fail, cluster_ok]
        )

    assert result.dlq_written == 1
    assert dlq.await_count == 1
    assert len(result.clusters) == 2
    # Both still qualify via frequency despite one LLM failure.
    assert len(result.qualifying) == 2
    failed = next(c for c in result.clusters if c.cluster_ref == "c-fail")
    assert failed.error is not None
    assert "LLM timeout" in failed.error


def test_classified_cluster_to_dict_shape() -> None:
    row = ClassifiedCluster(
        cluster_ref="r1",
        bucket_key="b",
        items=[{"question_id": "q1"}],
        unique_student_count=3,
        roster_size=12,
        freq_score=1.0,
        frequency_qualifies=True,
        criticality=8,
        criticality_qualifies=True,
        qualifies_for_mini_lecture=True,
        gso_id="gso-1",
    )
    d = row.to_dict()
    assert d["qualifies_for_mini_lecture"] is True
    assert d["question_ids"] == ["q1"]
