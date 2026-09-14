"""Teaching Innovation Record — T-138 (Flow 5 §3.10 #36, ARCH §8.6).

Adaptive per-teacher coaching, separate from student Cognitive DNA (Flow 9 /
M-18 — a different model in a different feature). Locked lifecycle:

    scoring run identifies a recurring weakness
        -> AI generates a coaching suggestion (never a grade/score)
        -> teacher acts on it or ignores it (tracked per weakness row)
        -> next time this weakness recurs, the AI adapts: a genuinely
           different angle if the last suggestion was ignored, otherwise a
           fresh natural tip

One row per (teacher, category, weakness_type) — the DB enforces this via a
unique constraint (T-129). A suggestion is generated the first time a
weakness is detected (matching the flow spec's own lifecycle diagram: no
"wait for N recurrences" gate) and again each time a previous round's
suggestion received a response; while a suggestion is still pending
(``teacher_response == NONE``), further recurrences just bump ``frequency``
silently — never spam a second suggestion before the teacher has reacted to
the first.
"""

from __future__ import annotations

import json
import re
from typing import Any, cast

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, PermissionDeniedError, ValidationError
from app.features.independent_users.models import IndependentUserRole
from app.features.independent_users.repository import IndependentUserRepository
from app.features.teacher_coaching.models import (
    IndependentTeacherAiMemory,
    SchoolTeacherAiMemory,
    TeacherResponseType,
)
from app.features.teacher_coaching.repository import (
    IndependentTeacherAiMemoryRepository,
    SchoolTeacherAiMemoryRepository,
)
from app.features.teacher_coaching.schemas import CoachingSuggestionRead
from app.features.users.models import UserRole
from app.features.users.repository import UserRepository
from app.infrastructure.llm.client import chat
from app.infrastructure.llm.prompts.teacher_coaching_v1 import (
    TeacherCoachingInput,
    TeacherCoachingOutput,
)
from app.infrastructure.llm.prompts.teacher_coaching_v1 import render as render_coaching

logger = structlog.get_logger(__name__)

_JSON_FENCE_RE = re.compile(r"^```(?:json)?|```$", re.MULTILINE)

# AI Learning/voice_quality are excluded: ai_learning baselines to 0 on every
# first version (T-134's own locked rule) which would look like a permanent
# "weakness" from day one, and voice_quality is null for most edits (text-only)
# so it would rarely have a comparable signal. The remaining five are always
# LLM-scored ints, a stable basis for a "this keeps coming up" pattern.
_TRACKABLE_DIMENSION_CAPS: dict[str, int] = {
    "originality": 10,
    "depth": 10,
    "cultural_relevance": 5,
    "engagement": 5,
    "alignment": 10,
}
_WEAK_THRESHOLD_FRACTION = 0.5
_CATEGORY = "quality_dimension"
_CONTEXT_ROWS_LIMIT = 5


def _parse_json_payload(raw: str) -> dict[str, Any]:
    text = _JSON_FENCE_RE.sub("", raw.strip()).strip()
    return cast(dict[str, Any], json.loads(text))


def _is_weak(dimension: str, score: object) -> bool:
    cap = _TRACKABLE_DIMENSION_CAPS.get(dimension)
    if cap is None or not isinstance(score, int):
        return False
    return score < cap * _WEAK_THRESHOLD_FRACTION


async def _generate_suggestion(
    *,
    weakness_type: str,
    frequency: int,
    last_suggestion: str | None,
    teacher_response: TeacherResponseType,
    region: str | None,
) -> str:
    prompt_input = TeacherCoachingInput(
        weakness_type=weakness_type,
        frequency=frequency,
        last_suggestion=last_suggestion,
        teacher_response=teacher_response.value,
        region=region,
    )
    prompt = render_coaching(prompt_input)
    raw = await chat(
        [
            {"role": "system", "content": prompt.system},
            {"role": "user", "content": prompt.user},
        ],
        task="scoring",
        temperature=prompt.temperature,
        max_tokens=prompt.max_tokens,
    )
    parsed = TeacherCoachingOutput.model_validate(_parse_json_payload(raw))
    return parsed.suggestion


def context_lines_from_memory(
    rows: list[SchoolTeacherAiMemory] | list[IndependentTeacherAiMemory],
) -> list[str]:
    """Shared formatting for both the scoring prompt (T-134) and the
    generation prompt (this ticket) — kept here so both features format
    Innovation Record context identically."""
    return [
        f"{row.weakness_type}: {row.last_suggestion} "
        f"(teacher previously {row.teacher_response.value} this suggestion, seen {row.frequency}x)"
        for row in rows
    ]


async def detect_and_track_weakness_school(
    session: AsyncSession, *, teacher_user_id: str, scores: dict[str, object], region: str | None
) -> None:
    repo = SchoolTeacherAiMemoryRepository(session)
    for dimension in _TRACKABLE_DIMENSION_CAPS:
        if not _is_weak(dimension, scores.get(dimension)):
            continue
        try:
            await _upsert_weakness_school(repo, teacher_user_id, dimension, region)
        except Exception as exc:
            # One dimension's suggestion failing (LLM hiccup) must never
            # block tracking the others.
            logger.warning(
                "teacher_coaching_weakness_track_failed",
                teacher_user_id=teacher_user_id,
                weakness_type=dimension,
                error=str(exc),
            )


async def _upsert_weakness_school(
    repo: SchoolTeacherAiMemoryRepository,
    teacher_user_id: str,
    weakness_type: str,
    region: str | None,
) -> None:
    existing = await repo.get_by_weakness(
        teacher_user_id=teacher_user_id, category=_CATEGORY, weakness_type=weakness_type
    )
    if existing is not None and existing.teacher_response == TeacherResponseType.NONE:
        # Still pending a response — bump frequency silently, no new suggestion.
        existing.frequency += 1
        await repo.update(existing)
        return

    suggestion = await _generate_suggestion(
        weakness_type=weakness_type,
        frequency=(existing.frequency + 1) if existing else 1,
        last_suggestion=existing.last_suggestion if existing else None,
        teacher_response=existing.teacher_response if existing else TeacherResponseType.NONE,
        region=region,
    )
    if existing is None:
        await repo.create(
            SchoolTeacherAiMemory(
                teacher_user_id=teacher_user_id,
                category=_CATEGORY,
                weakness_type=weakness_type,
                frequency=1,
                last_suggestion=suggestion,
                teacher_response=TeacherResponseType.NONE,
            )
        )
    else:
        existing.frequency += 1
        existing.last_suggestion = suggestion
        existing.teacher_response = TeacherResponseType.NONE
        await repo.update(existing)


async def detect_and_track_weakness_independent(
    session: AsyncSession, *, teacher_user_id: str, scores: dict[str, object]
) -> None:
    """Mirrors detect_and_track_weakness_school — no region (independent
    teachers have no region field, same N/A as T-134's scoring context)."""
    repo = IndependentTeacherAiMemoryRepository(session)
    for dimension in _TRACKABLE_DIMENSION_CAPS:
        if not _is_weak(dimension, scores.get(dimension)):
            continue
        try:
            await _upsert_weakness_independent(repo, teacher_user_id, dimension)
        except Exception as exc:
            logger.warning(
                "teacher_coaching_weakness_track_failed",
                teacher_user_id=teacher_user_id,
                weakness_type=dimension,
                error=str(exc),
            )


async def _upsert_weakness_independent(
    repo: IndependentTeacherAiMemoryRepository, teacher_user_id: str, weakness_type: str
) -> None:
    existing = await repo.get_by_weakness(
        teacher_user_id=teacher_user_id, category=_CATEGORY, weakness_type=weakness_type
    )
    if existing is not None and existing.teacher_response == TeacherResponseType.NONE:
        existing.frequency += 1
        await repo.update(existing)
        return

    suggestion = await _generate_suggestion(
        weakness_type=weakness_type,
        frequency=(existing.frequency + 1) if existing else 1,
        last_suggestion=existing.last_suggestion if existing else None,
        teacher_response=existing.teacher_response if existing else TeacherResponseType.NONE,
        region=None,
    )
    if existing is None:
        await repo.create(
            IndependentTeacherAiMemory(
                teacher_user_id=teacher_user_id,
                category=_CATEGORY,
                weakness_type=weakness_type,
                frequency=1,
                last_suggestion=suggestion,
                teacher_response=TeacherResponseType.NONE,
            )
        )
    else:
        existing.frequency += 1
        existing.last_suggestion = suggestion
        existing.teacher_response = TeacherResponseType.NONE
        await repo.update(existing)


async def get_generation_coaching_context_school(
    session: AsyncSession, *, teacher_user_id: str
) -> list[str]:
    """Pending (unactioned) suggestions only — the generation overlay nudges
    the teacher forward, unlike the scoring context (T-134) which reads all
    memory regardless of response status for a broader evaluator signal."""
    rows = await SchoolTeacherAiMemoryRepository(session).list_pending_for_teacher(teacher_user_id)
    return [row.last_suggestion for row in rows[:_CONTEXT_ROWS_LIMIT]]


async def get_generation_coaching_context_independent(
    session: AsyncSession, *, teacher_user_id: str
) -> list[str]:
    rows = await IndependentTeacherAiMemoryRepository(session).list_pending_for_teacher(
        teacher_user_id
    )
    return [row.last_suggestion for row in rows[:_CONTEXT_ROWS_LIMIT]]


async def list_current_suggestions_school(
    session: AsyncSession, teacher_user_id: str
) -> list[SchoolTeacherAiMemory]:
    return await SchoolTeacherAiMemoryRepository(session).list_pending_for_teacher(teacher_user_id)


async def list_current_suggestions_independent(
    session: AsyncSession, teacher_user_id: str
) -> list[IndependentTeacherAiMemory]:
    return await IndependentTeacherAiMemoryRepository(session).list_pending_for_teacher(
        teacher_user_id
    )


async def respond_to_suggestion_school(
    session: AsyncSession, *, teacher_user_id: str, memory_id: str, response: str
) -> SchoolTeacherAiMemory:
    if response not in ("acted", "ignored"):
        raise ValidationError("response must be 'acted' or 'ignored'")
    repo = SchoolTeacherAiMemoryRepository(session)
    memory = await repo.get_by_id(memory_id)
    if memory is None:
        raise NotFoundError("Coaching suggestion not found")
    if memory.teacher_user_id != teacher_user_id:
        raise PermissionDeniedError("Not your coaching suggestion")
    memory.teacher_response = TeacherResponseType(response)
    return await repo.update(memory)


async def respond_to_suggestion_independent(
    session: AsyncSession, *, teacher_user_id: str, memory_id: str, response: str
) -> IndependentTeacherAiMemory:
    if response not in ("acted", "ignored"):
        raise ValidationError("response must be 'acted' or 'ignored'")
    repo = IndependentTeacherAiMemoryRepository(session)
    memory = await repo.get_by_id(memory_id)
    if memory is None:
        raise NotFoundError("Coaching suggestion not found")
    if memory.teacher_user_id != teacher_user_id:
        raise PermissionDeniedError("Not your coaching suggestion")
    memory.teacher_response = TeacherResponseType(response)
    return await repo.update(memory)


def to_suggestion_read(
    memory: SchoolTeacherAiMemory | IndependentTeacherAiMemory,
) -> CoachingSuggestionRead:
    return CoachingSuggestionRead(
        id=memory.id,
        weakness_type=memory.weakness_type,
        suggestion=memory.last_suggestion,
        frequency=memory.frequency,
        updated_at=memory.updated_at,
    )


async def resolve_school_teacher_id(session: AsyncSession, claims: dict[str, object]) -> str:
    """Router-facing auth resolution — mirrors LectureWizardService's own
    ``_require_school_teacher`` (a free function here since this feature has
    no stateful service class, unlike lectures)."""
    user = await UserRepository(session).get_by_authentik_id(str(claims.get("sub", "")))
    if user is None or user.deleted_at is not None:
        raise NotFoundError("User profile not found")
    if user.role != UserRole.TEACHER:
        raise PermissionDeniedError("Teacher role required")
    if user.school_id is None:
        raise PermissionDeniedError("School teacher context required")
    return user.id


async def resolve_independent_teacher_id(session: AsyncSession, claims: dict[str, object]) -> str:
    user = await IndependentUserRepository(session).get_by_authentik_id(str(claims.get("sub", "")))
    if user is None or user.deleted_at is not None:
        raise NotFoundError("User profile not found")
    if user.role != IndependentUserRole.INDEPENDENT_TEACHER:
        raise PermissionDeniedError("Independent teacher role required")
    return user.id
