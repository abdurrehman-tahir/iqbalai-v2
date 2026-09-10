"""Unit tests for Qdrant tenant-filter chokepoint (ARCH §3.8)."""

from __future__ import annotations

from qdrant_client.models import FieldCondition, Filter, MatchValue

from app.infrastructure.rag.retriever import build_tenant_filter


def test_build_tenant_filter_none_when_empty() -> None:
    assert build_tenant_filter(None) is None
    assert build_tenant_filter({}) is None


def test_build_tenant_filter_school_id() -> None:
    result = build_tenant_filter({"school_id": "school-1"})
    assert isinstance(result, Filter)
    assert result.must is not None
    assert len(result.must) == 1
    condition = result.must[0]
    assert isinstance(condition, FieldCondition)
    assert condition.key == "school_id"
    assert isinstance(condition.match, MatchValue)
    assert condition.match.value == "school-1"
