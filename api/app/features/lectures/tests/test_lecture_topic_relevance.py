"""T-136 — topic relevance percentage (Flow 5 §3.8 #34, ARCH §7.3).

``embed`` is mocked with controlled vectors so the cosine-similarity math is
exactly verifiable, matching the suite's convention of never touching real
infra in unit tests.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock

import pytest

from app.features.lectures.topic_relevance import (
    LOW_RELEVANCE_WARNING_THRESHOLD,
    _cosine_similarity,
    compute_topic_relevance,
)


def _patch_embed(monkeypatch: pytest.MonkeyPatch, vectors: list[list[float]]) -> AsyncMock:
    embed_mock = AsyncMock(return_value=vectors)
    monkeypatch.setattr("app.features.lectures.topic_relevance.embed", embed_mock)
    return embed_mock


def test_cosine_similarity_identical_vectors_is_one() -> None:
    assert _cosine_similarity([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)


def test_cosine_similarity_orthogonal_vectors_is_zero() -> None:
    assert _cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)


def test_cosine_similarity_opposite_vectors_is_negative_one() -> None:
    assert _cosine_similarity([1.0, 0.0], [-1.0, 0.0]) == pytest.approx(-1.0)


def test_cosine_similarity_zero_vector_is_zero_not_a_crash() -> None:
    assert _cosine_similarity([0.0, 0.0], [1.0, 0.0]) == 0.0


@pytest.mark.asyncio
async def test_compute_topic_relevance_full_match_is_100(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_embed(monkeypatch, [[1.0, 0.0], [1.0, 0.0]])

    result = await compute_topic_relevance(topic="Newton's Laws", body="Newton's Laws content.")

    assert result == Decimal("100.00")


@pytest.mark.asyncio
async def test_compute_topic_relevance_unrelated_is_0(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_embed(monkeypatch, [[1.0, 0.0], [0.0, 1.0]])

    result = await compute_topic_relevance(topic="Newton's Laws", body="Unrelated content.")

    assert result == Decimal("0.00")


@pytest.mark.asyncio
async def test_compute_topic_relevance_partial_match_scales_to_percentage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # cos(45deg) ~= 0.7071 -> ~70.71%
    _patch_embed(monkeypatch, [[1.0, 0.0], [1.0, 1.0]])

    result = await compute_topic_relevance(topic="Newton's Laws", body="Somewhat related.")

    assert float(result) == pytest.approx(70.71, abs=0.01)


@pytest.mark.asyncio
async def test_compute_topic_relevance_negative_similarity_clips_to_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_embed(monkeypatch, [[1.0, 0.0], [-1.0, 0.0]])

    result = await compute_topic_relevance(topic="Newton's Laws", body="Opposite content.")

    assert result == Decimal("0.00")


@pytest.mark.asyncio
async def test_compute_topic_relevance_embeds_topic_and_body_together(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One batched embed() call for both texts, not two separate calls."""
    embed_mock = _patch_embed(monkeypatch, [[1.0, 0.0], [1.0, 0.0]])

    await compute_topic_relevance(topic="Newton's Laws", body="Newton's Laws content.")

    embed_mock.assert_awaited_once()
    call_args: Any = embed_mock.call_args.args[0]
    assert call_args == ["Newton's Laws", "Newton's Laws content."]


def test_low_relevance_warning_threshold_is_locked_at_70() -> None:
    """Flow 5 §3.8 locked rule: warning shown below 70%."""
    assert LOW_RELEVANCE_WARNING_THRESHOLD == 70.0
