"""Concept enrichment Celery tasks (T-189 beat; T-190 adds generation).

Platform-tier sweep (the per-concept cache is shared, not tenant-owned), so
``@shared_task`` like the framework refresh. DB access via ``run_db`` — the
disposable-engine pattern required outside the API process (CLAUDE.md rule 11).
"""

from __future__ import annotations

import structlog
from celery import shared_task

from app.db.celery_async import run_db
from app.features.concept_enrichment.cache import ENRICH_TASK_NAME, sweep_due_refreshes

logger = structlog.get_logger(__name__)


@shared_task(  # type: ignore[misc]
    name=ENRICH_TASK_NAME,
    queue="ml",
    acks_late=True,
    reject_on_worker_lost=True,
    soft_time_limit=120,
    time_limit=180,
)
def enrich_applications(application_id: str) -> str:
    """Generate one concept's enrichment (T-190). Idempotent: a fresh READY row
    or a row locked by another worker is skipped inside the generator. Failures
    are recorded on the row and retried by the daily sweep, not by Celery retry
    (avoids paying for repeated LLM calls in a tight loop)."""
    from app.features.concept_enrichment.generation import generate_enrichment

    outcome = run_db(lambda session: generate_enrichment(session, application_id))
    logger.info("concept_enrich_task_done", application_id=application_id, outcome=outcome)
    return outcome


@shared_task(name="concept.refresh_quarterly", queue="ml")  # type: ignore[misc]
def refresh_quarterly() -> int:
    """Daily beat: regenerate per-concept enrichment past CONCEPT_ENRICHMENT_CACHE_DAYS.

    Cadence is enforced in the sweep, not the beat (same as framework.refresh_quarterly).
    """
    return run_db(sweep_due_refreshes)
