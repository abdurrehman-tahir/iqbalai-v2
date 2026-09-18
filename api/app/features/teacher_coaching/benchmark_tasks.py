"""Celery beat task: weekly anonymized teacher benchmark recompute (T-139).

Cross-school (all of ``school`` schema) — not tenant-scoped, so a plain
``@shared_task`` + ``run_db`` rather than ``tenant_task`` (ARCH §10.6).
"""

from __future__ import annotations

import structlog
from celery import shared_task
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.celery_async import run_db

logger = structlog.get_logger(__name__)


@shared_task(name="benchmark.update_weekly", queue="ml")  # type: ignore[misc]
def update_weekly() -> dict[str, int]:
    """Weekly beat: recompute every (subject, grade_range, region) cohort's percentiles."""
    return run_db(_update_weekly)


async def _update_weekly(session: AsyncSession) -> dict[str, int]:
    from app.features.teacher_coaching.benchmark_service import (
        compute_and_store_weekly_benchmarks,
    )

    result = await compute_and_store_weekly_benchmarks(session)
    logger.info("benchmark_update_weekly_complete", **result)
    return result
