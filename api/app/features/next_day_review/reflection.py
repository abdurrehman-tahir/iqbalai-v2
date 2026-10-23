"""Reflective coaching prompt + teacher response — T-202 (Flow 7 §3.3 #49).

The question is generated with the review card; the teacher may answer by
text or voice (voice is transcribed through the existing teacher
voice-transcribe endpoint, then submitted as text). Answers land in
``teacher_ai_memory`` under ``reflective_response_pattern`` — the scoring
pipeline already feeds the teacher's top memory rows into the Innovation
Record context (M-10 T-134/T-138), which is how reflections inform future
coaching.
"""

from __future__ import annotations

import json
import re
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.next_day_review.categories import REFLECTIVE_RESPONSE_PATTERN
from app.features.next_day_review.schemas import ReviewClusterSnapshot
from app.features.teacher_coaching.models import SchoolTeacherAiMemory, TeacherResponseType
from app.features.teacher_coaching.repository import SchoolTeacherAiMemoryRepository
from app.infrastructure.llm.client import chat
from app.infrastructure.llm.prompts.next_day_review_reflective_v1 import (
    TASK_ID,
    ReflectiveInput,
    ReflectiveOutput,
    contains_grading_language,
    render,
)

logger = structlog.get_logger(__name__)

# One aggregate row per teacher: frequency = how many reflections they've given,
# last_suggestion = the latest question + answer (the pattern coaching reads).
REFLECTIVE_WEAKNESS_TYPE = "reflective_response"
MAX_ATTEMPTS = 2


def _parse(raw: str) -> dict[str, Any]:
    text = raw.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        text = fence.group(1).strip()
    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        text = text[start : end + 1]
    parsed: object = json.loads(text)
    if not isinstance(parsed, dict):
        raise ValueError("reflective response is not a JSON object")
    return parsed


async def generate_reflective_prompt(
    snapshots: list[ReviewClusterSnapshot],
    *,
    offering_label: str,
    lecture_topic: str,
    target_language: str,
) -> str:
    """Coaching question grounded in the review's clusters; ``""`` if it can't be made safely."""
    misconceptions = [s.representative_question for s in snapshots if s.representative_question]
    if not misconceptions:
        return ""
    prompt = render(
        ReflectiveInput(
            offering_label=offering_label[:300],
            lecture_topic=lecture_topic[:500],
            misconceptions=[m[:300] for m in misconceptions[:10]],
            target_language=target_language,  # type: ignore[arg-type]
        )
    )
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            raw = await chat(
                [
                    {"role": "system", "content": prompt.system},
                    {"role": "user", "content": prompt.user},
                ],
                task=TASK_ID,
                temperature=prompt.temperature,
                max_tokens=prompt.max_tokens,
            )
            question = ReflectiveOutput.model_validate(_parse(raw)).question.strip()
        except Exception as exc:
            # Deliberate: the reflective prompt is optional (spec Q1) — a failure
            # omits it rather than blocking the card.
            logger.warning("reflective_prompt_failed", attempt=attempt, error=str(exc))
            continue
        if contains_grading_language(question):
            logger.info("reflective_prompt_grading_rejected", attempt=attempt)
            continue
        return question
    return ""


async def record_reflection(
    session: AsyncSession,
    *,
    teacher_user_id: str,
    prompt: str,
    response: str,
) -> SchoolTeacherAiMemory:
    """Upsert the teacher's reflective-response memory row (T-202 #4)."""
    repo = SchoolTeacherAiMemoryRepository(session)
    entry = f"Q: {prompt}\nA: {response}"
    existing = await repo.get_by_weakness(
        teacher_user_id=teacher_user_id,
        category=REFLECTIVE_RESPONSE_PATTERN,
        weakness_type=REFLECTIVE_WEAKNESS_TYPE,
    )
    if existing is None:
        row = SchoolTeacherAiMemory(
            teacher_user_id=teacher_user_id,
            category=REFLECTIVE_RESPONSE_PATTERN,
            weakness_type=REFLECTIVE_WEAKNESS_TYPE,
            frequency=1,
            last_suggestion=entry,
            # ACTED: the teacher engaged; keeps it out of the pending-coaching list.
            teacher_response=TeacherResponseType.ACTED,
        )
        await repo.create(row)
        return row
    existing.frequency += 1
    existing.last_suggestion = entry
    existing.teacher_response = TeacherResponseType.ACTED
    await repo.update(existing)
    return existing
