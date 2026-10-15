"""Next-day review Celery tasks — T-196 overnight aggregation.

Beat ``review.aggregate_nightly`` @ 23:00 Asia/Karachi fans out one isolated
``review.aggregate_school`` task per active school so a slow/failing school
never blocks others (Flow 7 §3.1 / ARCH §10.3–§10.6).
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
from app.tasks.base import tenant_task

logger = structlog.get_logger(__name__)

AGGREGATE_NIGHTLY_TASK = "review.aggregate_nightly"
AGGREGATE_SCHOOL_TASK = "review.aggregate_school"


@shared_task(  # type: ignore[misc]
    name=AGGREGATE_NIGHTLY_TASK,
    queue="ml",
    acks_late=True,
    reject_on_worker_lost=True,
    soft_time_limit=120,
    time_limit=180,
)
def aggregate_nightly(review_date: str | None = None) -> int:
    """Fan out one per-school aggregation task for the Karachi calendar day.

    ``review_date`` is optional ISO ``YYYY-MM-DD`` (tests / manual re-runs);
    default is today in Asia/Karachi.
    """
    day = date.fromisoformat(review_date) if review_date else today_karachi()
    school_ids = run_db(list_active_school_ids)
    for school_id in school_ids:
        # Isolated apply_async — failures stay on that school's task (acceptance #2).
        aggregate_school.apply_async(
            kwargs={"school_id": school_id, "review_date": day.isoformat()}
        )
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
    """Aggregate one school's question events into (lecture, paragraph, chunk) buckets.

    Clustering / classification is T-197 — this task stops at buckets.
    """
    day = date.fromisoformat(review_date)

    async def _run(session: AsyncSession) -> dict[str, list[dict[str, Any]]]:
        return await aggregate_school_day(session, school_id, day)

    return run_db(_run)
