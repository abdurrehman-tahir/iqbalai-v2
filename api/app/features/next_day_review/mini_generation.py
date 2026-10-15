"""Mini-lecture generation from qualifying clusters — T-198 (Flow 7 §3.4).

Reuses Flow 5 ``run_lecture_generation`` (Pattern S) with ``allow_web_fallback=False``,
``lecture_type=mini``, and ``parent_lecture_id`` set. Word target 800–1200; hard
cost ceiling $0.50/mini (estimated from token-equivalent word count).
"""

from __future__ import annotations

from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.lectures.events import publish_lecture_event
from app.features.lectures.generation import run_lecture_generation
from app.features.lectures.models import LectureStatus, LectureType, SchoolLecture
from app.features.library.school_models import LibraryContentType, SchoolLibraryItem
from app.features.next_day_review.classification import ClassifiedCluster
from app.infrastructure.llm.prompts.mini_lecture_gen_v1 import (
    WORD_TARGET_MAX,
    WORD_TARGET_MIN,
)

logger = structlog.get_logger(__name__)

MINI_LECTURE_GENERATED = "mini_lecture.generated"
# Locked Flow 7 ceiling — approximate USD from word×token heuristic until
# stream_chat exposes usage (same order of magnitude as Groq 70B pricing).
MINI_COST_CEILING_USD = 0.50
_USD_PER_1K_WORDS = 0.08  # conservative; 1200 words ≈ $0.10 << $0.50


def estimate_mini_cost_usd(word_count: int) -> float:
    return (word_count / 1000.0) * _USD_PER_1K_WORDS


def word_count(text: str) -> int:
    return len(text.split())


def enforce_mini_limits(body: str) -> tuple[bool, str]:
    """Return (ok, reason). Cost ceiling is hard; word band is soft-logged."""
    words = word_count(body)
    cost = estimate_mini_cost_usd(words)
    if cost > MINI_COST_CEILING_USD:
        return False, f"cost_estimate_usd={cost:.4f} exceeds {MINI_COST_CEILING_USD}"
    if words > WORD_TARGET_MAX * 2:
        # Pathological overshoot — treat as failure rather than ship a novel.
        return False, f"word_count={words} far above target {WORD_TARGET_MAX}"
    return True, f"words={words} cost_usd={cost:.4f}"


def _cluster_topic(cluster: ClassifiedCluster) -> str:
    texts = [
        str(item.get("question_text") or "").strip()
        for item in cluster.items
        if item.get("question_text")
    ]
    sample = "; ".join(texts[:5]) if texts else cluster.cluster_ref
    return f"Mini-lecture correcting: {sample}"[:500]


async def _resolve_library_ids(session: AsyncSession, *, school_id: str) -> tuple[str, list[str]]:
    """Pick the school's first curriculum item + up to 3 reference books."""
    curr = await session.execute(
        select(SchoolLibraryItem)
        .where(
            SchoolLibraryItem.school_id == school_id,
            SchoolLibraryItem.content_type == LibraryContentType.CURRICULUM,
            SchoolLibraryItem.deleted_at.is_(None),
        )
        .order_by(SchoolLibraryItem.created_at.asc())
        .limit(1)
    )
    curriculum = curr.scalar_one_or_none()
    curriculum_id = curriculum.id if curriculum is not None else ""

    refs = await session.execute(
        select(SchoolLibraryItem)
        .where(
            SchoolLibraryItem.school_id == school_id,
            SchoolLibraryItem.content_type == LibraryContentType.REFERENCE,
            SchoolLibraryItem.deleted_at.is_(None),
        )
        .order_by(SchoolLibraryItem.created_at.asc())
        .limit(3)
    )
    reference_ids = [str(r.id) for r in refs.scalars().all()]
    return curriculum_id, reference_ids


async def generate_mini_for_cluster(
    session: AsyncSession,
    *,
    school_id: str,
    cluster: ClassifiedCluster,
) -> dict[str, Any] | None:
    """Create one mini-lecture for a qualifying cluster; return summary or None on skip."""
    if not cluster.qualifies_for_mini_lecture:
        return None
    if not cluster.items:
        return None

    parent_id = str(cluster.items[0].get("lecture_id") or "")
    parent = await session.get(SchoolLecture, parent_id) if parent_id else None
    if parent is None or parent.school_id != school_id:
        logger.warning(
            "mini_lecture_parent_missing",
            cluster_ref=cluster.cluster_ref,
            parent_id=parent_id,
        )
        return None

    topic = _cluster_topic(cluster)
    curriculum_id, reference_ids = await _resolve_library_ids(session, school_id=school_id)
    if not curriculum_id:
        logger.warning(
            "mini_lecture_no_curriculum",
            school_id=school_id,
            cluster_ref=cluster.cluster_ref,
        )
        return None

    mini = SchoolLecture(
        school_id=school_id,
        grade_subject_offering_id=parent.grade_subject_offering_id or cluster.gso_id,
        teacher_user_id=parent.teacher_user_id,
        title=topic[:500],
        topic=topic,
        lecture_type=LectureType.MINI,
        parent_lecture_id=parent.id,
        status=LectureStatus.GENERATING,
    )
    session.add(mini)
    await session.flush()

    version_id = await run_lecture_generation(
        session,
        lecture_id=mini.id,
        school_id=school_id,
        topic=topic,
        curriculum_id=curriculum_id,
        reference_book_ids=reference_ids,
        teaching_mode="auto",
        teacher_user_id=parent.teacher_user_id or "",
        target_language="en",
        allow_web_fallback=False,
    )

    await session.refresh(mini)
    body = ""
    if mini.current_version_id:
        from app.features.lectures.models import SchoolLectureVersion

        version = await session.get(SchoolLectureVersion, mini.current_version_id)
        if version is not None:
            body = version.body or ""

    ok, reason = enforce_mini_limits(body)
    words = word_count(body)
    if not ok:
        mini.status = LectureStatus.FAILED
        await session.flush()
        logger.error(
            "mini_lecture_limits_exceeded",
            lecture_id=mini.id,
            cluster_ref=cluster.cluster_ref,
            reason=reason,
        )
        return {
            "lecture_id": mini.id,
            "cluster_ref": cluster.cluster_ref,
            "status": "failed_limits",
            "reason": reason,
        }

    if words < WORD_TARGET_MIN or words > WORD_TARGET_MAX:
        logger.info(
            "mini_lecture_word_band_soft",
            lecture_id=mini.id,
            word_count=words,
            target_min=WORD_TARGET_MIN,
            target_max=WORD_TARGET_MAX,
        )

    await publish_lecture_event(
        event_type=MINI_LECTURE_GENERATED,
        payload={
            "lecture_id": mini.id,
            "parent_lecture_id": parent.id,
            "school_id": school_id,
            "teacher_user_id": parent.teacher_user_id or "",
            "tenant_type": "school",
            "cluster_ref": cluster.cluster_ref,
            "version_id": version_id,
            "word_count": words,
            "cost_estimate_usd": estimate_mini_cost_usd(words),
            "lecture_type": LectureType.MINI.value,
        },
    )
    logger.info(
        "mini_lecture_generated",
        lecture_id=mini.id,
        parent_lecture_id=parent.id,
        cluster_ref=cluster.cluster_ref,
        word_count=words,
    )
    return {
        "lecture_id": mini.id,
        "parent_lecture_id": parent.id,
        "cluster_ref": cluster.cluster_ref,
        "version_id": version_id,
        "word_count": words,
        "status": "generated",
    }


async def generate_minis_for_qualifying(
    session: AsyncSession,
    *,
    school_id: str,
    clusters: list[ClassifiedCluster],
) -> list[dict[str, Any]]:
    """Generate one mini-lecture per qualifying cluster (T-198)."""
    results: list[dict[str, Any]] = []
    for cluster in clusters:
        if not cluster.qualifies_for_mini_lecture:
            continue
        result = await generate_mini_for_cluster(session, school_id=school_id, cluster=cluster)
        if result is not None:
            results.append(result)
    return results
