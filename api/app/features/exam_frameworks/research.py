"""Pattern-A exam-framework research pipeline (T-093, ARCH §7.12/§8.21).

An explicit ordered pipeline (not a tool-choosing agent — the flow is fixed, so
STACK_LOCK's "ordered steps" guidance applies): SearXNG search -> web_fetch top
sources -> per-source LLM note extraction -> final LLM synthesis into the §3.5.2
study-plan structure. Every LLM call is metered; a hard USD ceiling halts the run
mid-way with a *partial* result rather than letting cost run away.

Copyright (ARCH §8.21): the synthesis prompt instructs the model to generate
*similar* practice problems and to cite every source — never to republish
copyrighted past papers verbatim. All fetched sources are recorded as citations.

Failures (no sources found, unparseable synthesis) raise :class:`ResearchError`;
the Celery task decides retry vs. terminal-fail. Network boundaries (SearXNG /
web fetch / the LLM) are the seams mocked in unit tests.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from decimal import Decimal

import structlog

from app.features.exam_frameworks.models import ExamFramework
from app.features.exam_frameworks.schemas import (
    ExamStrategy,
    FrameworkTopic,
    SourceCitation,
    WeeklyPacing,
)
from app.infrastructure.llm import client as llm
from app.infrastructure.rag.web_search import SearchResult, web_fetch, web_search

logger = structlog.get_logger(__name__)

_RESEARCH_TASK = "framework_research"

_SYNTHESIS_SYSTEM = (
    "You are an expert exam-preparation curriculum designer. From the provided "
    "source notes about a specific exam, produce a structured study plan. Analyse "
    "past-paper patterns and weight topics by how heavily they are tested. Generate "
    "ORIGINAL practice problems similar in style to public past papers — never copy "
    "copyrighted questions verbatim. Respond with ONLY a JSON object, no prose."
)


class ResearchError(Exception):
    """A hard, retryable failure in the research pipeline (no sources / bad output)."""


@dataclass
class ResearchOutcome:
    """The validated result parts of a research run (service assembles the plan)."""

    partial: bool
    topics: list[FrameworkTopic]
    weekly_pacing: list[WeeklyPacing]
    exam_strategy: ExamStrategy
    sources: list[SourceCitation]
    cost_usd: Decimal
    sources_count: int = field(init=False)

    def __post_init__(self) -> None:
        self.sources_count = len(self.sources)


def _search_queries(framework: ExamFramework) -> list[str]:
    """Derive the SearXNG queries for a framework from its metadata."""
    target = framework.exam_target
    region = framework.region
    return [
        f"{target} {region} past papers",
        f"{target} official syllabus",
        f"{target} study guide expert tips",
    ]


def _estimate_cost(total_tokens: int, usd_per_1k: float) -> Decimal:
    return (Decimal(total_tokens) / Decimal(1000)) * Decimal(str(usd_per_1k))


def _extract_json(text: str) -> dict[str, object]:
    """Parse a JSON object from an LLM response, tolerating ```json fences and a
    leading ``<think>...</think>`` reasoning block.

    Reasoning models (e.g. Groq's ``qwen/qwen3-32b``) emit their chain-of-thought in
    a ``<think>...</think>`` block before the answer; left in place it makes the
    payload invalid JSON. Strip any such blocks before parsing.
    """
    stripped = text.strip()
    stripped = re.sub(r"<think>.*?</think>", "", stripped, flags=re.DOTALL).strip()
    if stripped.startswith("```"):
        # Drop the opening fence line and any closing fence.
        stripped = stripped.split("\n", 1)[-1]
        if stripped.rstrip().endswith("```"):
            stripped = stripped.rsplit("```", 1)[0]
    stripped = stripped.strip()
    try:
        parsed = json.loads(stripped)
    except (ValueError, json.JSONDecodeError):
        # Reasoning may still bracket the JSON (e.g. an unclosed <think> prefix or a
        # trailing note). Fall back to the first balanced top-level {...} object.
        candidate = _first_json_object(stripped)
        if candidate is None:
            raise ResearchError("synthesis returned no parseable JSON object")
        try:
            parsed = json.loads(candidate)
        except (ValueError, json.JSONDecodeError) as exc:
            raise ResearchError(f"synthesis returned non-JSON output: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ResearchError("synthesis JSON was not an object")
    return parsed


def _first_json_object(text: str) -> str | None:
    """Return the first balanced ``{...}`` substring, or ``None`` if none is complete.

    A brace counter that ignores braces inside JSON strings — used to recover the
    study-plan object when the model brackets it with stray reasoning/prose.
    """
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    in_str = False
    escaped = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


async def _gather_sources(
    framework: ExamFramework, max_sources: int
) -> list[tuple[SearchResult, str]]:
    """Search + fetch up to ``max_sources`` unique pages with non-empty text."""
    seen: set[str] = set()
    gathered: list[tuple[SearchResult, str]] = []
    for query in _search_queries(framework):
        for hit in await web_search(query, max_results=max_sources):
            if hit.url in seen:
                continue
            seen.add(hit.url)
            body = await web_fetch(hit.url)
            if body:
                gathered.append((hit, body))
            if len(gathered) >= max_sources:
                return gathered
    return gathered


async def run_research(
    framework: ExamFramework,
    *,
    max_sources: int,
    ceiling_usd: float,
    usd_per_1k: float,
) -> ResearchOutcome:
    """Execute the research pipeline for a framework.

    Args:
        framework: the DRAFT framework being researched.
        max_sources: how many top sources to fetch + synthesise (§8.21: 10-20).
        ceiling_usd: hard USD cost cap — the run halts + flags partial if crossed.
        usd_per_1k: blended token price used to estimate spend from LLM usage.

    Returns a :class:`ResearchOutcome`. Raises :class:`ResearchError` on no sources
    or unparseable synthesis output.
    """
    gathered = await _gather_sources(framework, max_sources)
    if not gathered:
        raise ResearchError("no usable sources found for framework research")

    ceiling = Decimal(str(ceiling_usd))
    cost = Decimal("0")
    notes: list[str] = []
    used: list[SourceCitation] = []
    partial = False

    # Per-source extraction — metered so the ceiling can halt mid-run (§8.21).
    for hit, body in gathered:
        if cost >= ceiling:
            partial = True
            logger.warning(
                "framework_research_cost_ceiling_hit",
                framework_id=framework.id,
                cost_usd=str(cost),
                sources_used=len(used),
            )
            break
        result = await llm.chat_with_usage(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Extract exam-relevant facts from this source: topics tested, "
                        "their frequency in past papers, key concepts, common pitfalls, "
                        "and expert tips. Be concise."
                    ),
                },
                {"role": "user", "content": f"Source: {hit.title}\n\n{body}"},
            ],
            task=_RESEARCH_TASK,
            temperature=0.3,
        )
        cost += _estimate_cost(result.total_tokens, usd_per_1k)
        notes.append(result.text)
        used.append(SourceCitation(url=hit.url, title=hit.title or hit.url))

    if not notes:
        # Ceiling was already exhausted before the first source could be processed.
        raise ResearchError("cost ceiling exhausted before any source was analysed")

    # Final synthesis into the §3.5.2 structure (topics / pacing / strategy).
    synthesis = await llm.chat_with_usage(
        messages=[
            {"role": "system", "content": _SYNTHESIS_SYSTEM},
            {
                "role": "user",
                "content": (
                    f"Exam: {framework.exam_target}\nRegion: {framework.region}\n"
                    f"Grade range: {framework.target_grade_range}\n\n"
                    "Source notes:\n" + "\n---\n".join(notes) + "\n\n"
                    "Return ONLY a JSON object (no markdown fences, no commentary) with "
                    "EXACTLY these keys and value types:\n"
                    "- topics: array of objects, each with topic_name (string), "
                    "priority_weight (number between 0 and 1), exam_frequency (string), "
                    "recommended_hours (integer), key_concepts (array of strings), "
                    "common_pitfalls (array of strings), past_paper_patterns (string), "
                    "practice_problems_generated (array of strings), expert_tips "
                    "(array of strings).\n"
                    "- weekly_pacing: array of objects, each with week_from_exam "
                    "(integer), focus_topics (array of strings), hours_estimated "
                    "(integer).\n"
                    "- exam_strategy: object with time_allocation (string), "
                    "scoring_strategy (string), common_mistakes (array of strings)."
                ),
            },
        ],
        task=_RESEARCH_TASK,
        temperature=0.4,
        # Reasoning models (qwen3) spend part of the budget on a <think> block, so
        # give headroom or the study-plan JSON gets truncated mid-object.
        max_tokens=8192,
    )
    cost += _estimate_cost(synthesis.total_tokens, usd_per_1k)
    if cost >= ceiling:
        partial = True

    raw = _extract_json(synthesis.text)
    raw_topics = raw.get("topics", [])
    raw_pacing = raw.get("weekly_pacing", [])
    if not isinstance(raw_topics, list) or not isinstance(raw_pacing, list):
        raise ResearchError("synthesis JSON 'topics'/'weekly_pacing' must be lists")
    try:
        topics = [FrameworkTopic.model_validate(t) for t in raw_topics]
        weekly_pacing = [WeeklyPacing.model_validate(w) for w in raw_pacing]
        exam_strategy = ExamStrategy.model_validate(raw.get("exam_strategy", {}))
    except ValueError as exc:
        raise ResearchError(f"synthesis JSON failed §3.5.2 validation: {exc}") from exc

    logger.info(
        "framework_research_synthesised",
        framework_id=framework.id,
        topic_count=len(topics),
        sources_used=len(used),
        cost_usd=str(cost),
        partial=partial,
    )
    return ResearchOutcome(
        partial=partial,
        topics=topics,
        weekly_pacing=weekly_pacing,
        exam_strategy=exam_strategy,
        sources=used,
        cost_usd=cost,
    )
