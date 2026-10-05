"""Per-concept enrichment cache policy + refresh sweep — T-189 (flow-6 §3.10 / §5.9).

The cache is PER CONCEPT (one row per concept_id + tenant_type), never per
student. ``CONCEPT_ENRICHMENT_CACHE_DAYS`` (default 90) sets the age after
which the daily beat regenerates an entry; students keep being served the
existing content while the refresh runs (§5.9 "serves with an updated badge").
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.features.concept_enrichment.models import (
    ConceptApplicationStatus,
    SchoolConceptApplication,
)
from app.features.concept_enrichment.repository import ConceptApplicationRepository

logger = structlog.get_logger(__name__)

# Registered by the worker (concept_enrichment/tasks.py, T-190); enqueued by
# name so the cache layer never imports the LLM generation path.
ENRICH_TASK_NAME = "concept.enrich_applications"
# A PENDING row untouched this long is assumed lost (worker crash) and re-enqueued.
LOST_PENDING_AFTER = timedelta(hours=1)
REFRESH_BATCH_LIMIT = 200


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def cache_cutoff(now: datetime | None = None) -> datetime:
    days = get_settings().CONCEPT_ENRICHMENT_CACHE_DAYS
    return (now or _utcnow()) - timedelta(days=days)


def is_stale(row: SchoolConceptApplication, now: datetime | None = None) -> bool:
    """A READY entry older than the configured cache age."""
    if row.status != ConceptApplicationStatus.READY or row.generated_at is None:
        return False
    return row.generated_at < cache_cutoff(now)


def enqueue_enrichment(application_id: str) -> None:
    """Fire-and-forget enqueue on the ``ml`` queue (ARCH §10.6)."""
    from app.infrastructure.celery.celery_app import celery_app

    celery_app.send_task(ENRICH_TASK_NAME, args=[application_id], queue="ml")


async def sweep_due_refreshes(session: AsyncSession, *, now: datetime | None = None) -> int:
    """Daily beat body: enqueue regeneration for stale / failed / lost entries."""
    current = now or _utcnow()
    rows = await ConceptApplicationRepository(session).list_due_for_refresh(
        stale_before=cache_cutoff(current),
        lost_pending_before=current - LOST_PENDING_AFTER,
        limit=REFRESH_BATCH_LIMIT,
    )
    for row in rows:
        enqueue_enrichment(row.id)
    logger.info("concept_enrichment_refresh_sweep", enqueued=len(rows))
    return len(rows)
