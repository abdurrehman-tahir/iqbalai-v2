"""T-135 — system-wide originality check (Flow 5 §3.7 #33, ARCH §7.15).

Covers ``check_and_index_school_originality`` (global cross-school index +
plagiarism-flag threshold) and ``check_and_index_independent_originality``
(tenant-isolated, own prior versions only, never flagged). Qdrant/embedding
calls are mocked at their import site in ``originality.py`` — matches the
suite's convention of never touching real infra in unit tests.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from app.features.lectures.originality import (
    SIMILARITY_FLAG_THRESHOLD,
    check_and_index_independent_originality,
    check_and_index_school_originality,
)

_FAKE_VECTOR = [0.1, 0.2, 0.3]


def _patch_embed(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    embed_mock = AsyncMock(return_value=[_FAKE_VECTOR])
    monkeypatch.setattr("app.features.lectures.originality.embed", embed_mock)
    return embed_mock


@pytest.mark.asyncio
async def test_school_originality_full_score_when_no_matches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_embed(monkeypatch)
    monkeypatch.setattr(
        "app.features.lectures.originality.search_by_vector", AsyncMock(return_value=[])
    )
    upsert_mock = AsyncMock()
    monkeypatch.setattr("app.features.lectures.originality.upsert_point", upsert_mock)

    result = await check_and_index_school_originality(
        school_id="school-1",
        teacher_id="teacher-1",
        lecture_id="lec-1",
        version_id="ver-1",
        body="Some lecture content.",
    )

    assert result.max_similarity == 0.0
    assert result.originality_score == 1  # 1 - 0 = fully original
    assert result.is_flagged is False
    assert result.matched_version_id is None
    upsert_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_school_originality_below_threshold_not_flagged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_embed(monkeypatch)
    monkeypatch.setattr(
        "app.features.lectures.originality.search_by_vector",
        AsyncMock(return_value=[{"id": "ver-other", "score": 0.5, "payload": {}}]),
    )
    monkeypatch.setattr("app.features.lectures.originality.upsert_point", AsyncMock())

    result = await check_and_index_school_originality(
        school_id="school-1",
        teacher_id="teacher-1",
        lecture_id="lec-1",
        version_id="ver-1",
        body="Some lecture content.",
    )

    assert result.max_similarity == 0.5
    assert float(result.originality_score) == pytest.approx(0.5, abs=1e-3)
    assert result.is_flagged is False
    assert result.matched_version_id is None


@pytest.mark.asyncio
async def test_school_originality_above_threshold_flags_and_identifies_match(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_embed(monkeypatch)
    monkeypatch.setattr(
        "app.features.lectures.originality.search_by_vector",
        AsyncMock(
            return_value=[{"id": "ver-matched", "score": 0.93, "payload": {"school_id": "s2"}}]
        ),
    )
    monkeypatch.setattr("app.features.lectures.originality.upsert_point", AsyncMock())

    result = await check_and_index_school_originality(
        school_id="school-1",
        teacher_id="teacher-1",
        lecture_id="lec-1",
        version_id="ver-1",
        body="Copied content.",
    )

    assert result.max_similarity == 0.93
    assert result.max_similarity > SIMILARITY_FLAG_THRESHOLD
    assert result.is_flagged is True
    assert result.matched_version_id == "ver-matched"


@pytest.mark.asyncio
async def test_school_originality_excludes_own_lecture_from_search(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The lecture's own prior versions must never count as a match against
    itself — verified by asserting the exclude filter passed to Qdrant."""
    _patch_embed(monkeypatch)
    search_mock = AsyncMock(return_value=[])
    monkeypatch.setattr("app.features.lectures.originality.search_by_vector", search_mock)
    monkeypatch.setattr("app.features.lectures.originality.upsert_point", AsyncMock())

    await check_and_index_school_originality(
        school_id="school-1",
        teacher_id="teacher-1",
        lecture_id="lec-1",
        version_id="ver-2",
        body="Edited content.",
    )

    call_kwargs: dict[str, Any] = search_mock.call_args.kwargs
    assert call_kwargs["exclude"] == {"lecture_id": "lec-1"}
    # Global, cross-school search — no school_id/tenant filter on the search.
    assert call_kwargs.get("tenant_filter") is None


@pytest.mark.asyncio
async def test_school_originality_indexes_the_new_version_after_searching(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_embed(monkeypatch)
    monkeypatch.setattr(
        "app.features.lectures.originality.search_by_vector", AsyncMock(return_value=[])
    )
    upsert_mock = AsyncMock()
    monkeypatch.setattr("app.features.lectures.originality.upsert_point", upsert_mock)

    await check_and_index_school_originality(
        school_id="school-1",
        teacher_id="teacher-1",
        lecture_id="lec-1",
        version_id="ver-1",
        body="Some lecture content.",
    )

    upsert_mock.assert_awaited_once()
    call_args = upsert_mock.call_args
    assert call_args.args[1] == "ver-1"  # point_id == this version's id
    payload = call_args.kwargs["payload"]
    assert payload["school_id"] == "school-1"
    assert payload["teacher_id"] == "teacher-1"
    assert payload["lecture_id"] == "lec-1"


@pytest.mark.asyncio
async def test_independent_originality_never_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    """Even a near-identical match never raises a flag for independent
    teachers — no cross-teacher comparison, no plagiarism_flags table there."""
    _patch_embed(monkeypatch)
    monkeypatch.setattr(
        "app.features.lectures.originality.search_by_vector",
        AsyncMock(return_value=[{"id": "ver-self-old", "score": 0.99, "payload": {}}]),
    )
    monkeypatch.setattr("app.features.lectures.originality.upsert_point", AsyncMock())

    result = await check_and_index_independent_originality(
        teacher_id="teacher-1",
        lecture_id="lec-1",
        version_id="ver-2",
        body="Reused content.",
    )

    assert result.max_similarity == 0.99
    assert result.is_flagged is False
    assert result.matched_version_id is None


@pytest.mark.asyncio
async def test_independent_originality_scopes_search_to_own_lecture_versions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_embed(monkeypatch)
    search_mock = AsyncMock(return_value=[])
    monkeypatch.setattr("app.features.lectures.originality.search_by_vector", search_mock)
    monkeypatch.setattr("app.features.lectures.originality.upsert_point", AsyncMock())

    await check_and_index_independent_originality(
        teacher_id="teacher-1",
        lecture_id="lec-1",
        version_id="ver-1",
        body="Content.",
    )

    call_kwargs: dict[str, Any] = search_mock.call_args.kwargs
    assert call_kwargs["tenant_filter"] == {"content_type": "lecture_version"}
    assert call_kwargs["exclude"] == {"lecture_id": "lec-1"}
