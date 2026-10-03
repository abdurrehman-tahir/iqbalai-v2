"""Concept enrichment Celery tasks (T-189 beat; T-190 adds generation).

Platform-tier sweep (the per-concept cache is shared, not tenant-owned), so
``@shared_task`` like the framework refresh. DB access via ``run_db`` — the
disposable-engine pattern required outside the API process (CLAUDE.md rule 11).
"""

from __future__ import annotations

import structlog
from celery import shared_task

from app.db.celery_async import run_db
from app.features.concept_enrichment.cache import sweep_due_refreshes

logger = structlog.get_logger(__name__)


@shared_task(name="concept.refresh_quarterly", queue="ml")  # type: ignore[misc]
def refresh_quarterly() -> int:
    """Daily beat: regenerate per-concept enrichment past CONCEPT_ENRICHMENT_CACHE_DAYS.

    Cadence is enforced in the sweep, not the beat (same as framework.refresh_quarterly).
    """
    return run_db(sweep_due_refreshes)
