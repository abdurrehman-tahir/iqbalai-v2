"""Tests for curriculum topic extraction — T-057."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.features.library.curriculum_topic_extract import (
    extract_curriculum_topic_tree,
    extract_curriculum_topic_tree_sync,
)


@pytest.mark.asyncio
async def test_extract_parses_valid_llm_json() -> None:
    llm_json = """
    {
      "chapters": [
        {
          "title": "Mechanics",
          "sections": [
            {"title": "Motion", "sub_topics": ["Speed", "Velocity"]}
          ]
        }
      ]
    }
    """
    with patch(
        "app.features.library.curriculum_topic_extract.chat",
        new_callable=AsyncMock,
        return_value=llm_json,
    ):
        result = await extract_curriculum_topic_tree(
            document_text="Chapter 1 Mechanics",
            title="Physics 9",
            language="en",
        )

    assert result["parse_degraded"] is False
    assert len(result["chapters"]) == 1
    assert result["chapters"][0]["sections"][0]["sub_topics"] == ["Speed", "Velocity"]


@pytest.mark.asyncio
async def test_extract_returns_degraded_tree_on_llm_failure() -> None:
    with patch(
        "app.features.library.curriculum_topic_extract.chat",
        new_callable=AsyncMock,
        side_effect=RuntimeError("provider down"),
    ):
        result = await extract_curriculum_topic_tree(
            document_text="Some curriculum text",
            title="Physics 9",
        )

    assert result["parse_degraded"] is True
    assert result["chapters"] == []
    assert "provider down" in str(result["parse_error"])


def test_extract_sync_wrapper_delegates_to_async() -> None:
    degraded = {"chapters": [], "parse_degraded": True, "parse_error": "empty"}
    with patch(
        "app.features.library.curriculum_topic_extract.extract_curriculum_topic_tree",
        new_callable=AsyncMock,
        return_value=degraded,
    ):
        with patch("app.features.library.curriculum_topic_extract.asyncio.run") as mock_run:
            mock_run.side_effect = lambda coro: degraded
            result = extract_curriculum_topic_tree_sync(
                document_text="text",
                title="Physics 9",
            )

    assert result == degraded
    mock_run.assert_called_once()
