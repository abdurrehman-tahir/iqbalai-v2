"""Regenerate a review's mini-lecture, honouring skipped clusters — T-203 (Flow 7 §3.6).

The teacher's "Regenerate" picks the review's top cluster that has NOT been
skipped (Critical first, then largest) and runs the T-198 generator on it
again. A new mini-lecture is created and becomes the card's preview; students
who already received an earlier mini keep it unless the teacher re-publishes
(Flow 7 §5.4).
"""

from __future__ import annotations

from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.lectures.models import SchoolLecture
from app.features.next_day_review.classification import ClassifiedCluster
from app.features.next_day_review.mini_generation import generate_mini_for_cluster
from app.features.next_day_review.models import LectureReview, SkippedCluster
from app.features.next_day_review.schemas import ReviewClusterSnapshot

logger = structlog.get_logger(__name__)


async def skipped_refs(session: AsyncSession, review_id: str) -> set[str]:
    result = await session.execute(
        select(SkippedCluster.cluster_ref).where(SkippedCluster.review_id == review_id)
    )
    return {str(ref) for ref in result.scalars().all()}


def pick_cluster(
    snapshots: list[ReviewClusterSnapshot], skipped: set[str]
) -> ReviewClusterSnapshot | None:
    """Top non-skipped cluster — the one a regenerated mini-lecture should target."""
    eligible = [s for s in snapshots if s.cluster_ref not in skipped]
    eligible.sort(key=lambda s: (s.column != "critical", -s.question_count))
    return eligible[0] if eligible else None


def as_classified(snap: ReviewClusterSnapshot, gso_id: str) -> ClassifiedCluster:
    """Rebuild the generator's input from the stored snapshot."""
    items: list[dict[str, Any]] = [
        {
            "question_id": q.question_id,
            "user_id": q.student_user_id,
            "lecture_id": snap.lecture_id,
            "paragraph_id": q.paragraph_id,
            "source_chunk_id": q.source_chunk_id,
            "question_text": q.question_text,
            "occurred_at": q.occurred_at,
        }
        for q in snap.questions
    ]
    critical = snap.column == "critical"
    return ClassifiedCluster(
        cluster_ref=snap.cluster_ref,
        bucket_key=snap.cluster_ref,
        items=items,
        unique_student_count=snap.unique_student_count,
        roster_size=0,
        freq_score=snap.freq_score,
        frequency_qualifies=not critical,
        criticality=snap.criticality,
        criticality_qualifies=critical,
        qualifies_for_mini_lecture=True,
        gso_id=gso_id,
    )


async def regenerate_review_mini(session: AsyncSession, *, review_id: str) -> dict[str, Any] | None:
    """Generate a fresh mini-lecture for the review's top non-skipped cluster."""
    review = await session.get(LectureReview, review_id)
    if review is None:
        logger.warning("review_regenerate_missing", review_id=review_id)
        return None
    lecture = await session.get(SchoolLecture, review.lecture_id)
    if lecture is None:
        return None
    snapshots = [ReviewClusterSnapshot.model_validate(c) for c in review.clusters_jsonb or []]
    target = pick_cluster(snapshots, await skipped_refs(session, review_id))
    if target is None:
        logger.info("review_regenerate_all_skipped", review_id=review_id)
        return None

    result = await generate_mini_for_cluster(
        session, school_id=lecture.school_id, cluster=as_classified(target, review.gso_id)
    )
    if result is None or result.get("status") != "generated":
        logger.warning("review_regenerate_failed", review_id=review_id, result=result)
        await session.commit()
        return result

    new_mini_id = str(result["lecture_id"])
    review.mini_lecture_id = new_mini_id
    review.clusters_jsonb = [
        {**c, "mini_lecture_id": new_mini_id} if c.get("cluster_ref") == target.cluster_ref else c
        for c in review.clusters_jsonb or []
    ]
    await session.commit()
    logger.info(
        "review_mini_regenerated",
        review_id=review_id,
        cluster_ref=target.cluster_ref,
        mini_lecture_id=new_mini_id,
    )
    return result
