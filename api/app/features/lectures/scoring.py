"""7-dimension quality scoring pipeline (T-134, Flow 5 §3.6 #32, ARCH §7.10).

Triggered as a Celery task on every ``lecture.version.created`` (v1 generation
AND every subsequent teacher save). A single, separate LLM call scores the
saved version across 7 dimensions (max 55) and writes ``scores_jsonb``.

Also runs the two other scoring-pipeline sub-checks that share this trigger:
originality-index checking (T-135, ``originality.py``) and topic-relevance
scoring (T-136, ``topic_relevance.py``) — each its own decoupled try/except so
a failure in one never discards results already computed by the others.

Best-effort, matching the established pattern for post-save/post-generation
LLM enrichment steps (``generate_lecture_teacher_tips``,
``suggest_diagrams_from_chunks``): a scoring failure must never affect the
lecture or version that already saved successfully, so failures are logged
and swallowed rather than raised/retried.
"""

from __future__ import annotations

import difflib
import json
import re
from decimal import Decimal
from typing import Any, cast

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.lectures.independent_repository import (
    IndependentLectureEditSessionRepository,
    IndependentLectureVersionRepository,
)
from app.features.lectures.models import (
    IndependentLecture,
    IndependentLectureVersion,
    SchoolLecture,
    SchoolLecturePlagiarismFlag,
    SchoolLectureVersion,
)
from app.features.lectures.originality import (
    check_and_index_independent_originality,
    check_and_index_school_originality,
)
from app.features.lectures.repository import (
    LectureEditSessionRepository,
    LectureVersionRepository,
)
from app.features.lectures.topic_relevance import compute_topic_relevance
from app.features.teacher_coaching.models import (
    IndependentTeacherAiMemory,
    SchoolTeacherAiMemory,
)
from app.features.teacher_coaching.service import (
    detect_and_track_weakness_independent,
    detect_and_track_weakness_school,
)
from app.features.teacher_onboarding.models import TeacherProfile
from app.infrastructure.llm.client import chat
from app.infrastructure.llm.prompts.lecture_scoring_v1 import (
    LectureScoringInput,
    LectureScoringOutput,
)
from app.infrastructure.llm.prompts.lecture_scoring_v1 import render as render_scoring
from app.infrastructure.notifications.system import notify_all_platform_admins

logger = structlog.get_logger(__name__)

_JSON_FENCE_RE = re.compile(r"^```(?:json)?|```$", re.MULTILINE)
_MAX_MEMORY_CONTEXT_ROWS = 5
_MAX_BODY_CHARS = 6000
_MAX_DIFF_CHARS = 4000
_MAX_DIFF_LINES = 200

_DIMENSION_CAPS: dict[str, int] = {
    "originality": 10,
    "depth": 10,
    "cultural_relevance": 5,
    "engagement": 5,
    "alignment": 10,
    "voice_quality": 5,
    "ai_learning": 10,
}


def _parse_json_payload(raw: str) -> dict[str, Any]:
    text = _JSON_FENCE_RE.sub("", raw.strip()).strip()
    return cast(dict[str, Any], json.loads(text))


def _clamp(value: int, cap: int) -> int:
    """Defends the locked dimension caps against a non-compliant LLM response
    (Pydantic already guarantees ``value`` is an int by the time this runs —
    this only guards the numeric range, not the type)."""
    return max(0, min(cap, value))


def _build_diff(original: str, edited: str) -> str:
    if original == edited:
        return "(no textual change from the first version)"
    lines = list(
        difflib.unified_diff(
            original.splitlines(),
            edited.splitlines(),
            lineterm="",
            n=1,
        )
    )[:_MAX_DIFF_LINES]
    return "\n".join(lines)[:_MAX_DIFF_CHARS]


def _memory_context_lines(
    rows: list[SchoolTeacherAiMemory] | list[IndependentTeacherAiMemory],
) -> list[str]:
    return [
        f"{row.weakness_type}: {row.last_suggestion} "
        f"(teacher previously {row.teacher_response.value} this suggestion, seen {row.frequency}x)"
        for row in rows
    ]


async def _score_version(
    *,
    topic: str,
    original_body: str,
    edited_body: str,
    edit_summary: list[str] | None,
    is_first_version: bool,
    active_ms: int,
    edits_count: int,
    char_delta: int,
    teacher_region: str | None,
    innovation_record_context: list[str],
) -> dict[str, object]:
    """Core scoring call — tenant-agnostic, given already-resolved inputs."""
    is_voice_edit = edit_summary is not None and "Applied voice edit" in edit_summary

    prompt_input = LectureScoringInput(
        topic=(topic or "Untitled lecture")[:500],
        original_body=original_body[:_MAX_BODY_CHARS] or "(empty)",
        edited_body=edited_body[:_MAX_BODY_CHARS] or "(empty)",
        diff=_build_diff(original_body, edited_body),
        edit_summary=list(edit_summary or [])[:20],
        active_ms=max(active_ms, 0),
        edits_count=max(edits_count, 0),
        char_delta=max(char_delta, 0),
        teacher_region=teacher_region,
        innovation_record_context=innovation_record_context[:_MAX_MEMORY_CONTEXT_ROWS],
        is_first_version=is_first_version,
    )
    prompt = render_scoring(prompt_input)
    raw = await chat(
        [
            {"role": "system", "content": prompt.system},
            {"role": "user", "content": prompt.user},
        ],
        task="scoring",
        temperature=prompt.temperature,
        max_tokens=prompt.max_tokens,
    )
    parsed = LectureScoringOutput.model_validate(_parse_json_payload(raw))

    scores: dict[str, object] = {
        "originality": _clamp(parsed.originality, _DIMENSION_CAPS["originality"]),
        "depth": _clamp(parsed.depth, _DIMENSION_CAPS["depth"]),
        "cultural_relevance": _clamp(
            parsed.cultural_relevance, _DIMENSION_CAPS["cultural_relevance"]
        ),
        "engagement": _clamp(parsed.engagement, _DIMENSION_CAPS["engagement"]),
        "alignment": _clamp(parsed.alignment, _DIMENSION_CAPS["alignment"]),
        # Locked rules (Flow 5 §3.6), enforced here rather than trusted to the
        # LLM: voice_quality is null for text-only edits; ai_learning is a
        # deterministic 0 baseline on the first version.
        "voice_quality": (
            _clamp(parsed.voice_quality or 0, _DIMENSION_CAPS["voice_quality"])
            if is_voice_edit
            else None
        ),
        "ai_learning": 0
        if is_first_version
        else _clamp(parsed.ai_learning, _DIMENSION_CAPS["ai_learning"]),
    }
    scores["total"] = sum(v for v in scores.values() if isinstance(v, int))
    return scores


async def _raise_plagiarism_flag(
    session: AsyncSession,
    *,
    lecture_version_id: str,
    teacher_user_id: str | None,
    matched_lecture_version_id: str | None,
    similarity_score: Decimal,
) -> None:
    """Creates the admin-only flag row + notifies Platform Admins (T-135, #33).

    The notification carries only a similarity percentage — never the matched
    teacher's identity (Flow 5 §3.7 privacy rule). The flag row itself stores
    ``matched_lecture_version_id`` for eventual admin triage (Phase 2 — out of
    scope here per the ticket)."""
    flag = SchoolLecturePlagiarismFlag(
        lecture_version_id=lecture_version_id,
        teacher_user_id=teacher_user_id,
        matched_lecture_version_id=matched_lecture_version_id,
        similarity_score=similarity_score,
    )
    session.add(flag)
    await notify_all_platform_admins(
        session,
        template_key="system.plagiarism_flagged",
        params={"similarity_pct": str(int(similarity_score * 100))},
        metadata={"flag_id": flag.id},
    )


async def score_school_lecture_version(
    session: AsyncSession, *, lecture_id: str, school_id: str, version_id: str
) -> None:
    lecture = await session.get(SchoolLecture, lecture_id)
    if lecture is None or lecture.school_id != school_id:
        logger.warning("lecture_scoring_lecture_not_found", lecture_id=lecture_id)
        return
    version = await session.get(SchoolLectureVersion, version_id)
    if version is None or version.lecture_id != lecture_id:
        logger.warning(
            "lecture_scoring_version_not_found", lecture_id=lecture_id, version_id=version_id
        )
        return

    first_version = await LectureVersionRepository(session).get_first_for_lecture(lecture_id)
    if first_version is None:
        logger.warning("lecture_scoring_no_first_version", lecture_id=lecture_id)
        return

    edit_sessions = await LectureEditSessionRepository(session).list_by_version_id(version_id)

    teacher_region: str | None = None
    memory_context: list[str] = []
    if lecture.teacher_user_id:
        profile = await session.get(TeacherProfile, lecture.teacher_user_id)
        teacher_region = profile.region_province if profile else None

        result = await session.execute(
            select(SchoolTeacherAiMemory)
            .where(SchoolTeacherAiMemory.teacher_user_id == lecture.teacher_user_id)
            .order_by(SchoolTeacherAiMemory.frequency.desc())
            .limit(_MAX_MEMORY_CONTEXT_ROWS)
        )
        memory_context = _memory_context_lines(list(result.scalars().all()))

    try:
        scores = await _score_version(
            topic=lecture.title,
            original_body=first_version.body,
            edited_body=version.body,
            edit_summary=version.edit_summary,
            is_first_version=version.version == 1,
            active_ms=sum(s.active_ms for s in edit_sessions),
            edits_count=sum(s.edits_count for s in edit_sessions),
            char_delta=sum(s.char_delta for s in edit_sessions),
            teacher_region=teacher_region,
            innovation_record_context=memory_context,
        )
    except Exception as exc:
        logger.warning(
            "lecture_scoring_failed", lecture_id=lecture_id, version_id=version_id, error=str(exc)
        )
        return

    version.scores_jsonb = scores

    # T-135: originality is a separate, embedding-based check (no LLM) — its
    # own try/except so a failure here doesn't discard the 7-dim scores above.
    try:
        originality = await check_and_index_school_originality(
            school_id=school_id,
            teacher_id=lecture.teacher_user_id or "",
            lecture_id=lecture_id,
            version_id=version_id,
            body=version.body,
        )
        version.originality_score = originality.originality_score
        if originality.is_flagged:
            await _raise_plagiarism_flag(
                session,
                lecture_version_id=version_id,
                teacher_user_id=lecture.teacher_user_id,
                matched_lecture_version_id=originality.matched_version_id,
                similarity_score=Decimal(str(round(originality.max_similarity, 3))),
            )
    except Exception as exc:
        logger.warning(
            "lecture_originality_check_failed",
            lecture_id=lecture_id,
            version_id=version_id,
            error=str(exc),
        )

    # T-136: topic relevance is its own decoupled try/except too — another
    # embedding-based check, independent of both the 7-dim scores and the
    # originality check above.
    try:
        version.topic_relevance_pct = await compute_topic_relevance(
            topic=lecture.topic, body=version.body
        )
    except Exception as exc:
        logger.warning(
            "lecture_topic_relevance_check_failed",
            lecture_id=lecture_id,
            version_id=version_id,
            error=str(exc),
        )

    # T-138: Teaching Innovation Record — detects recurring weak dimensions
    # and (re)generates a coaching suggestion. Its own try/except, same
    # decoupled pattern as originality/topic-relevance above; writes its own
    # rows via teacher_coaching's repository, no version-column mutation
    # here, so nothing to roll into the commit below beyond what it already
    # committed itself.
    try:
        await detect_and_track_weakness_school(
            session,
            teacher_user_id=lecture.teacher_user_id or "",
            scores=scores,
            region=teacher_region,
        )
    except Exception as exc:
        logger.warning(
            "teacher_coaching_check_failed",
            lecture_id=lecture_id,
            version_id=version_id,
            error=str(exc),
        )

    await session.commit()
    logger.info(
        "lecture_scoring_complete",
        lecture_id=lecture_id,
        version_id=version_id,
        total=scores["total"],
    )


async def score_independent_lecture_version(
    session: AsyncSession, *, lecture_id: str, version_id: str
) -> None:
    """Mirrors ``score_school_lecture_version`` — no school_id scoping, no
    teacher region (independent teachers have no region field, per
    ``IndependentTeacherProfile`` — flagged as N/A rather than assumed)."""
    lecture = await session.get(IndependentLecture, lecture_id)
    if lecture is None:
        logger.warning("lecture_scoring_lecture_not_found", lecture_id=lecture_id)
        return
    version = await session.get(IndependentLectureVersion, version_id)
    if version is None or version.lecture_id != lecture_id:
        logger.warning(
            "lecture_scoring_version_not_found", lecture_id=lecture_id, version_id=version_id
        )
        return

    first_version = await IndependentLectureVersionRepository(session).get_first_for_lecture(
        lecture_id
    )
    if first_version is None:
        logger.warning("lecture_scoring_no_first_version", lecture_id=lecture_id)
        return

    edit_sessions = await IndependentLectureEditSessionRepository(session).list_by_version_id(
        version_id
    )

    memory_context: list[str] = []
    if lecture.teacher_user_id:
        result = await session.execute(
            select(IndependentTeacherAiMemory)
            .where(IndependentTeacherAiMemory.teacher_user_id == lecture.teacher_user_id)
            .order_by(IndependentTeacherAiMemory.frequency.desc())
            .limit(_MAX_MEMORY_CONTEXT_ROWS)
        )
        memory_context = _memory_context_lines(list(result.scalars().all()))

    try:
        scores = await _score_version(
            topic=lecture.title,
            original_body=first_version.body,
            edited_body=version.body,
            edit_summary=version.edit_summary,
            is_first_version=version.version == 1,
            active_ms=sum(s.active_ms for s in edit_sessions),
            edits_count=sum(s.edits_count for s in edit_sessions),
            char_delta=sum(s.char_delta for s in edit_sessions),
            teacher_region=None,
            innovation_record_context=memory_context,
        )
    except Exception as exc:
        logger.warning(
            "lecture_scoring_failed", lecture_id=lecture_id, version_id=version_id, error=str(exc)
        )
        return

    version.scores_jsonb = scores

    # T-135: same decoupled try/except as the school variant. No plagiarism
    # flag here — independent originality is tenant-isolated (own prior
    # versions only), and lecture_plagiarism_flags is a school-schema table.
    try:
        originality = await check_and_index_independent_originality(
            teacher_id=lecture.teacher_user_id or "",
            lecture_id=lecture_id,
            version_id=version_id,
            body=version.body,
        )
        version.originality_score = originality.originality_score
    except Exception as exc:
        logger.warning(
            "lecture_originality_check_failed",
            lecture_id=lecture_id,
            version_id=version_id,
            error=str(exc),
        )

    try:
        version.topic_relevance_pct = await compute_topic_relevance(
            topic=lecture.topic, body=version.body
        )
    except Exception as exc:
        logger.warning(
            "lecture_topic_relevance_check_failed",
            lecture_id=lecture_id,
            version_id=version_id,
            error=str(exc),
        )

    try:
        await detect_and_track_weakness_independent(
            session, teacher_user_id=lecture.teacher_user_id or "", scores=scores
        )
    except Exception as exc:
        logger.warning(
            "teacher_coaching_check_failed",
            lecture_id=lecture_id,
            version_id=version_id,
            error=str(exc),
        )

    await session.commit()
    logger.info(
        "lecture_scoring_complete",
        lecture_id=lecture_id,
        version_id=version_id,
        total=scores["total"],
    )
