"""Unit tests for the Pattern-A research pipeline — T-093.

The three network seams (SearXNG ``web_search``, ``web_fetch``, and the metered
``llm.chat_with_usage``) are mocked; the tests exercise the orchestration logic:
happy-path synthesis, the cost-ceiling halt (partial), the no-sources failure, and
JSON-fence tolerance. Business orchestration is what these guard — not the network.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import pytest

from app.features.exam_frameworks import research
from app.features.exam_frameworks.models import ExamFramework
from app.features.exam_frameworks.research import ResearchError, run_research
from app.infrastructure.llm.client import ChatUsage
from app.infrastructure.rag.web_search import SearchResult

_VALID_SYNTHESIS = {
    "topics": [
        {
            "topic_name": "Kinematics",
            "priority_weight": 0.9,
            "exam_frequency": "every_year",
            "recommended_hours": 12,
            "key_concepts": ["velocity", "acceleration"],
            "common_pitfalls": ["sign errors"],
            "past_paper_patterns": "Always a numerical in Q1.",
            "practice_problems_generated": ["A car accelerates..."],
            "expert_tips": ["Draw the motion diagram first."],
        }
    ],
    "weekly_pacing": [{"week_from_exam": 8, "focus_topics": ["Kinematics"], "hours_estimated": 10}],
    "exam_strategy": {
        "time_allocation": "2 min per MCQ",
        "scoring_strategy": "Attempt all MCQs first",
        "common_mistakes": ["Skipping units"],
    },
}


def _framework() -> ExamFramework:
    fw = ExamFramework(
        id="fw-1",
        name="Matric Punjab — Physics",
        exam_target="Matric Punjab Board — Physics",
        region="Punjab",
        target_grade_range=[9, 10],
        language="en",
        created_by="admin-1",
    )
    fw.created_at = datetime.now(timezone.utc)
    fw.updated_at = datetime.now(timezone.utc)
    return fw


def _patch_network(
    monkeypatch: pytest.MonkeyPatch,
    *,
    hits: list[SearchResult],
    bodies: dict[str, str],
    synthesis_text: str,
    tokens: int = 100,
) -> None:
    """Stub the three seams: search returns ``hits``, fetch maps url->body, LLM
    returns an extraction note per source then ``synthesis_text`` for the final call."""

    async def _fake_search(query: str, max_results: int = 15) -> list[SearchResult]:
        return hits

    async def _fake_fetch(url: str) -> str:
        return bodies.get(url, "")

    async def _fake_chat(messages: Any, task: str = "", **kwargs: Any) -> ChatUsage:
        # The final synthesis call is identified by its system prompt; every other
        # call is a per-source extraction (robust even when the ceiling halts early).
        system = messages[0]["content"]
        is_synthesis = "curriculum designer" in system
        return ChatUsage(
            text=synthesis_text if is_synthesis else "extracted note",
            prompt_tokens=tokens,
            completion_tokens=tokens,
        )

    monkeypatch.setattr(research, "web_search", _fake_search)
    monkeypatch.setattr(research, "web_fetch", _fake_fetch)
    # Patch the client module attribute directly (research calls llm.chat_with_usage).
    monkeypatch.setattr("app.infrastructure.llm.client.chat_with_usage", _fake_chat)


@pytest.mark.asyncio
async def test_run_research_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    hits = [
        SearchResult(title="Past papers", url="https://a.test", snippet="s"),
        SearchResult(title="Syllabus", url="https://b.test", snippet="s"),
    ]
    _patch_network(
        monkeypatch,
        hits=hits,
        bodies={"https://a.test": "body a", "https://b.test": "body b"},
        synthesis_text=json.dumps(_VALID_SYNTHESIS),
    )

    outcome = await run_research(_framework(), max_sources=15, ceiling_usd=10.0, usd_per_1k=0.001)

    assert outcome.partial is False
    assert outcome.sources_count == 2
    assert outcome.topics[0].topic_name == "Kinematics"
    assert outcome.weekly_pacing[0].week_from_exam == 8
    assert outcome.exam_strategy.scoring_strategy == "Attempt all MCQs first"
    assert outcome.cost_usd > Decimal("0")


@pytest.mark.asyncio
async def test_run_research_tolerates_json_fence(monkeypatch: pytest.MonkeyPatch) -> None:
    hits = [SearchResult(title="Past papers", url="https://a.test", snippet="s")]
    fenced = "```json\n" + json.dumps(_VALID_SYNTHESIS) + "\n```"
    _patch_network(
        monkeypatch,
        hits=hits,
        bodies={"https://a.test": "body a"},
        synthesis_text=fenced,
    )

    outcome = await run_research(_framework(), max_sources=15, ceiling_usd=10.0, usd_per_1k=0.001)

    assert outcome.topics[0].topic_name == "Kinematics"


@pytest.mark.asyncio
async def test_run_research_halts_partial_on_cost_ceiling(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hits = [
        SearchResult(title="s1", url="https://a.test", snippet="s"),
        SearchResult(title="s2", url="https://b.test", snippet="s"),
        SearchResult(title="s3", url="https://c.test", snippet="s"),
    ]
    # Each LLM call bills 1000+1000 tokens -> $0.002 at $0.001/1k. A $0.001 ceiling
    # is crossed after the first source, so the rest are skipped -> partial.
    _patch_network(
        monkeypatch,
        hits=hits,
        bodies={
            "https://a.test": "body a",
            "https://b.test": "body b",
            "https://c.test": "body c",
        },
        synthesis_text=json.dumps(_VALID_SYNTHESIS),
        tokens=1000,
    )

    outcome = await run_research(_framework(), max_sources=15, ceiling_usd=0.001, usd_per_1k=0.001)

    assert outcome.partial is True
    # Only the first source was analysed before the ceiling halted the loop.
    assert outcome.sources_count == 1


@pytest.mark.asyncio
async def test_run_research_no_sources_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_network(
        monkeypatch,
        hits=[SearchResult(title="s", url="https://a.test", snippet="s")],
        bodies={},  # every fetch returns empty -> no usable sources
        synthesis_text=json.dumps(_VALID_SYNTHESIS),
    )

    with pytest.raises(ResearchError, match="no usable sources"):
        await run_research(_framework(), max_sources=15, ceiling_usd=10.0, usd_per_1k=0.001)


@pytest.mark.asyncio
async def test_run_research_bad_json_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_network(
        monkeypatch,
        hits=[SearchResult(title="s", url="https://a.test", snippet="s")],
        bodies={"https://a.test": "body a"},
        synthesis_text="not json at all",
    )

    with pytest.raises(ResearchError, match="no parseable JSON"):
        await run_research(_framework(), max_sources=15, ceiling_usd=10.0, usd_per_1k=0.001)
