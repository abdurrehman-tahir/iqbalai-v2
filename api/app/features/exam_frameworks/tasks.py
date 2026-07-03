"""Exam-framework Celery tasks — Pattern-A research run (T-093).

Platform-tier work (frameworks are platform-shared, no ``school_id``), so this uses
``@shared_task`` like the other platform sweeps (graduation/invites) rather than
``@tenant_task``. The task is a thin wrapper (STACK_LOCK §layer-purity): all business
logic lives in :class:`ExamFrameworkService`. Retries on transient research failures
up to 3×; on exhaustion the framework is reverted to DRAFT and the job flagged
``research_failed`` (Acceptance #7).
"""

from __future__ import annotations

import asyncio

import structlog
from celery import shared_task

from app.features.exam_frameworks.research import ResearchError

logger = structlog.get_logger(__name__)


@shared_task(  # type: ignore[misc]
    bind=True,
    name="exam_frameworks.research_framework",
    queue="ml",
    max_retries=3,
    default_retry_delay=60,
    acks_late=True,
    reject_on_worker_lost=True,
    soft_time_limit=1500,
    time_limit=1800,
)
def research_framework(self: object, framework_id: str, job_id: str) -> str:
    """Run the AI research pipeline for a framework, retrying transient failures."""
    try:
        return asyncio.run(_run_research_async(framework_id, job_id))
    except ResearchError as exc:
        retries = self.request.retries  # type: ignore[attr-defined]
        max_retries = self.max_retries  # type: ignore[attr-defined]
        if retries >= max_retries:
            # Retries exhausted — flag the job and revert the framework to DRAFT.
            asyncio.run(_fail_research_async(framework_id, job_id, str(exc)))
            return "research_failed"
        raise self.retry(exc=exc)  # type: ignore[attr-defined]


async def _run_research_async(framework_id: str, job_id: str) -> str:
    from app.db.session import async_session_factory
    from app.features.exam_frameworks.service import ExamFrameworkService

    async with async_session_factory() as session:
        svc = ExamFrameworkService(session)
        status = await svc.run_and_persist_research(framework_id, job_id)
    logger.info("framework_research_task_complete", framework_id=framework_id, status=status.value)
    return status.value


async def _fail_research_async(framework_id: str, job_id: str, error: str) -> None:
    from app.db.session import async_session_factory
    from app.features.exam_frameworks.service import ExamFrameworkService

    async with async_session_factory() as session:
        svc = ExamFrameworkService(session)
        await svc.mark_research_failed(framework_id, job_id, error)
