"""Unit tests for the T-135 originality-checking additions to retriever.py:
``_build_search_filter`` (exclusion support), ``search_by_vector``, and
``upsert_point``. The Qdrant wire client itself is mocked — same convention
as the rest of the suite (features monkeypatch retriever functions at their
own call site; this file covers the retriever internals directly since
they're new and otherwise uncovered).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from qdrant_client.models import FieldCondition, Filter, MatchValue

from app.infrastructure.rag.retriever import (
    _build_search_filter,
    search_by_vector,
    upsert_point,
)


def test_build_search_filter_none_when_both_empty() -> None:
    assert _build_search_filter(None, None) is None
    assert _build_search_filter({}, {}) is None


def test_build_search_filter_must_and_must_not() -> None:
    result = _build_search_filter({"school_id": "s1"}, {"lecture_id": "lec-1"})
    assert isinstance(result, Filter)
    assert isinstance(result.must, list)
    assert isinstance(result.must_not, list)
    must_condition = result.must[0]
    must_not_condition = result.must_not[0]
    assert isinstance(must_condition, FieldCondition)
    assert isinstance(must_not_condition, FieldCondition)
    assert must_condition.key == "school_id"
    assert isinstance(must_condition.match, MatchValue)
    assert must_condition.match.value == "s1"
    assert must_not_condition.key == "lecture_id"


def test_build_search_filter_exclude_only() -> None:
    result = _build_search_filter(None, {"lecture_id": "lec-1"})
    assert isinstance(result, Filter)
    assert result.must is None
    assert isinstance(result.must_not, list)


@pytest.mark.asyncio
async def test_search_by_vector_returns_scored_results(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_hit = MagicMock(id="ver-2", score=0.91, payload={"lecture_id": "lec-2"})
    fake_client = AsyncMock()
    fake_client.search = AsyncMock(return_value=[fake_hit])
    fake_client.close = AsyncMock()

    monkeypatch.setattr("app.infrastructure.rag.retriever._get_client", lambda: fake_client)

    results = await search_by_vector("some_collection", [0.1, 0.2], top_k=10)

    assert len(results) == 1
    assert results[0]["id"] == "ver-2"
    assert results[0]["score"] == 0.91
    fake_client.close.assert_awaited()


@pytest.mark.asyncio
async def test_search_by_vector_returns_empty_on_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """Missing collection (first-ever check) or any Qdrant error -> no matches,
    never an exception — the caller treats this as "fully original"."""
    fake_client = AsyncMock()
    fake_client.search = AsyncMock(side_effect=RuntimeError("collection not found"))
    fake_client.close = AsyncMock()

    monkeypatch.setattr("app.infrastructure.rag.retriever._get_client", lambda: fake_client)

    results = await search_by_vector("some_collection", [0.1, 0.2])

    assert results == []


@pytest.mark.asyncio
async def test_upsert_point_creates_collection_when_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_collections_response = MagicMock(collections=[])
    fake_client = AsyncMock()
    fake_client.get_collections = AsyncMock(return_value=fake_collections_response)
    fake_client.create_collection = AsyncMock()
    fake_client.upsert = AsyncMock()
    fake_client.close = AsyncMock()

    monkeypatch.setattr("app.infrastructure.rag.retriever._get_client", lambda: fake_client)

    await upsert_point("new_collection", "point-1", [0.1, 0.2, 0.3], {"lecture_id": "lec-1"})

    fake_client.create_collection.assert_awaited_once()
    fake_client.upsert.assert_awaited_once()
    call_kwargs: dict[str, Any] = fake_client.upsert.call_args.kwargs
    assert call_kwargs["collection_name"] == "new_collection"
    assert len(call_kwargs["points"]) == 1


@pytest.mark.asyncio
async def test_upsert_point_skips_create_when_collection_exists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    existing = MagicMock()
    existing.name = "already_there"
    fake_collections_response = MagicMock(collections=[existing])
    fake_client = AsyncMock()
    fake_client.get_collections = AsyncMock(return_value=fake_collections_response)
    fake_client.create_collection = AsyncMock()
    fake_client.upsert = AsyncMock()
    fake_client.close = AsyncMock()

    monkeypatch.setattr("app.infrastructure.rag.retriever._get_client", lambda: fake_client)

    await upsert_point("already_there", "point-1", [0.1], {})

    fake_client.create_collection.assert_not_awaited()
    fake_client.upsert.assert_awaited_once()
