"""Next-day review Celery tasks — T-196 aggregation + T-197 cluster/classify.

Beat ``review.aggregate_nightly`` @ 23:00 Asia/Karachi fans out one isolated
``review.classify_school`` task per active school so a slow/failing school
never blocks others (Flow 7 §3.1 / ARCH §10.3–§10.6). Each school task
aggregates → clusters (cosine ≥0.80) → classifies (freq + criticality) and
writes DLQ rows on cluster-level LLM failure without aborting the batch.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import structlog
from celery import shared_task  # type: ignore[import-untyped]
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.celery_async import run_db
from app.features.next_day_review.aggregation import (
    aggregate_school_day,
    list_active_school_ids,
    today_karachi,
)
from app.features.next_day_review.classification import classify_clusters
from app.features.next_day_review.clustering import cluster_all_buckets
from app.features.next_day_review.mini_generation import generate_minis_for_qualifying
from app.tasks.base import tenant_task

logger = structlog.get_logger(__name__)

AGGREGATE_NIGHTLY_TASK = "review.aggregate_nightly"
AGGREGATE_SCHOOL_TASK = "review.aggregate_school"
CLASSIFY_SCHOOL_TASK = "review.classify_school"


@shared_task(  # type: ignore[misc]
    name=AGGREGATE_NIGHTLY_TASK,
    queue="ml",
    acks_late=True,
    reject_on_worker_lost=True,
    soft_time_limit=120,
    time_limit=180,
)
def aggregate_nightly(review_date: str | None = None) -> int:
    """Fan out one per-school classify pipeline for the Karachi calendar day.

    ``review_date`` is optional ISO ``YYYY-MM-DD`` (tests / manual re-runs);
    default is today in Asia/Karachi.
    """
    day = date.fromisoformat(review_date) if review_date else today_karachi()
    school_ids = run_db(list_active_school_ids)
    for school_id in school_ids:
        # Isolated apply_async — failures stay on that school's task (T-196 #2).
        classify_school.apply_async(kwargs={"school_id": school_id, "review_date": day.isoformat()})
    logger.info(
        "review_aggregate_nightly_fanned_out",
        school_count=len(school_ids),
        review_date=day.isoformat(),
    )
    return len(school_ids)


@tenant_task(
    name=AGGREGATE_SCHOOL_TASK,
    queue="ml",
    acks_late=True,
    reject_on_worker_lost=True,
    soft_time_limit=600,
    time_limit=720,
)
def aggregate_school(school_id: str, review_date: str) -> dict[str, list[dict[str, Any]]]:
    """Aggregate one school's question events into (lecture, paragraph, chunk) buckets."""
    day = date.fromisoformat(review_date)

    async def _run(session: AsyncSession) -> dict[str, list[dict[str, Any]]]:
        return await aggregate_school_day(session, school_id, day)

    return run_db(_run)


@tenant_task(
    name=CLASSIFY_SCHOOL_TASK,
    queue="ml",
    acks_late=True,
    reject_on_worker_lost=True,
    soft_time_limit=900,
    time_limit=1080,
)
def classify_school(school_id: str, review_date: str) -> dict[str, Any]:
    """Aggregate → cluster → classify for one school; flag mini-lecture candidates.

    Mini-lecture generation itself is T-198 — this only sets
    ``qualifies_for_mini_lecture`` on each cluster.
    """
    day = date.fromisoformat(review_date)

    async def _run(session: AsyncSession) -> dict[str, Any]:
        buckets = await aggregate_school_day(session, school_id, day)
        clusters = await cluster_all_buckets(buckets)
        classified = await classify_clusters(session, school_id=school_id, clusters=clusters)
        # T-198: one mini-lecture per qualifying cluster (web fallback off).
        minis = await generate_minis_for_qualifying(
            session, school_id=school_id, clusters=classified.qualifying
        )
        return {
            "school_id": school_id,
            "review_date": day.isoformat(),
            "bucket_count": len(buckets),
            "cluster_count": len(classified.clusters),
            "qualifying_count": len(classified.qualifying),
            "dlq_written": classified.dlq_written,
            "mini_lecture_count": len(minis),
            "mini_lectures": minis,
            "clusters": [c.to_dict() for c in classified.clusters],
            "qualifying_cluster_refs": [c.cluster_ref for c in classified.qualifying],
        }

    return run_db(_run)
