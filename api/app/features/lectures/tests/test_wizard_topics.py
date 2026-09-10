"""Unit tests for topic-tree flatten (T-114)."""

from __future__ import annotations

from app.features.lectures.service import _tree_is_degraded, flatten_topic_tree


def test_degraded_when_empty_or_flagged() -> None:
    assert _tree_is_degraded(None) is True
    assert _tree_is_degraded({"chapters": [], "parse_degraded": False}) is True
    assert _tree_is_degraded({"chapters": [{"title": "A"}], "parse_degraded": True}) is True
    assert _tree_is_degraded({"chapters": [{"title": "A"}], "parse_degraded": False}) is False


def test_flatten_chapter_only() -> None:
    topics = flatten_topic_tree({"chapters": [{"title": "Intro"}]})
    assert len(topics) == 1
    assert topics[0].path == "Intro"
