"""Curriculum structured topic-tree extraction — T-057."""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any

import structlog

from app.infrastructure.llm.client import chat
from app.infrastructure.llm.prompts.curriculum_topic_extract_v1 import (
    PROMPT_VERSION,
    CurriculumTopicExtractInput,
    CurriculumTopicExtractOutput,
    render,
)

logger = structlog.get_logger(__name__)

_JSON_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def _parse_json_payload(raw: str) -> dict[str, Any]:
    text = _JSON_FENCE_RE.sub("", raw.strip()).strip()
    return json.loads(text)


def _degraded_tree(error: str) -> dict[str, object]:
    return {
        "chapters": [],
        "parse_degraded": True,
        "parse_error": error[:500],
        "prompt_version": PROMPT_VERSION,
    }


def _success_tree(output: CurriculumTopicExtractOutput) -> dict[str, object]:
    return {
        **output.model_dump(mode="json"),
        "parse_degraded": False,
        "parse_error": None,
        "prompt_version": PROMPT_VERSION,
    }


async def extract_curriculum_topic_tree(
    *,
    document_text: str,
    title: str,
    language: str = "en",
) -> dict[str, object]:
    """Run LLM structured parse; never raises — returns degraded tree on failure."""
    if not document_text.strip():
        return _degraded_tree("No document text available for topic extraction")

    lang = language if language in ("en", "ur", "sd", "ps") else "en"
    prompt = render(
        CurriculumTopicExtractInput(
            title=title,
            language=lang,  # type: ignore[arg-type]
            document_text=document_text,
        )
    )

    try:
        raw = await chat(
            messages=[
                {"role": "system", "content": prompt.system},
                {"role": "user", "content": prompt.user},
            ],
            task="curriculum_topic_extract",
            temperature=prompt.temperature,
            max_tokens=prompt.max_tokens,
        )
        payload = _parse_json_payload(raw)
        output = CurriculumTopicExtractOutput.model_validate(payload)
        if not output.chapters:
            return _degraded_tree("LLM returned an empty topic tree")
        logger.info(
            "curriculum_topic_extract_ok",
            title=title,
            chapter_count=len(output.chapters),
            prompt_version=PROMPT_VERSION,
        )
        return _success_tree(output)
    except Exception as exc:
        logger.warning(
            "curriculum_topic_extract_failed",
            title=title,
            error=str(exc),
            prompt_version=PROMPT_VERSION,
        )
        return _degraded_tree(str(exc))


def extract_curriculum_topic_tree_sync(
    *,
    document_text: str,
    title: str,
    language: str = "en",
) -> dict[str, object]:
    """Sync wrapper for Celery ingestion tasks."""
    return asyncio.run(
        extract_curriculum_topic_tree(
            document_text=document_text,
            title=title,
            language=language,
        )
    )
