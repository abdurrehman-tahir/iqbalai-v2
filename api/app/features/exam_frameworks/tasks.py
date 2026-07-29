"""Exam-framework Celery tasks — Pattern-A research run (T-093).

Platform-tier work (frameworks are platform-shared, no ``school_id``), so this uses
``@shared_task`` like the other platform sweeps (graduation/invites) rather than
``@tenant_task``. The task is a thin wrapper (STACK_LOCK §layer-purity): all business
logic lives in :class:`ExamFrameworkService`. Retries on transient research failures
up to 3×; on exhaustion the framework is reverted to DRAFT and the job flagged
``research_failed`` (Acceptance #7).

DB access goes through ``run_db`` (disposable engine per ``asyncio.run``) — the API's
module-level ``async_session_factory`` cannot be reused across Celery ``asyncio.run``
calls or you get "Future attached to a different loop" and the DRAFT revert never
lands, leaving the UI stuck on Researching.
"""

from __future__ import annotations

import structlog
from celery import shared_task
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.celery_async import run_db
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
    from celery.exceptions import SoftTimeLimitExceeded, TimeLimitExceeded

    try:
        return run_db(lambda session: _run_research(session, framework_id, job_id))
    except (SoftTimeLimitExceeded, TimeLimitExceeded):
        raise
    except Exception as exc:
        # Network blips / bad LLM model / page fetch must follow the same
        # retry→DRAFT path as ResearchError — otherwise the framework stays
        # stuck in RESEARCHING forever.
        research_exc = (
            exc
            if isinstance(exc, ResearchError)
            else ResearchError(f"research pipeline failure: {exc}")
        )
        retries = self.request.retries  # type: ignore[attr-defined]
        max_retries = self.max_retries  # type: ignore[attr-defined]
        if retries >= max_retries:
            run_db(lambda session: _fail_research(session, framework_id, job_id, str(research_exc)))
            return "research_failed"
        raise self.retry(exc=research_exc)  # type: ignore[attr-defined]


async def _run_research(session: AsyncSession, framework_id: str, job_id: str) -> str:
    from app.features.exam_frameworks.service import ExamFrameworkService

    svc = ExamFrameworkService(session)
    status = await svc.run_and_persist_research(framework_id, job_id)
    logger.info("framework_research_task_complete", framework_id=framework_id, status=status.value)
    return status.value


async def _fail_research(session: AsyncSession, framework_id: str, job_id: str, error: str) -> None:
    from app.features.exam_frameworks.service import ExamFrameworkService

    svc = ExamFrameworkService(session)
    await svc.mark_research_failed(framework_id, job_id, error)


@shared_task(name="framework.approval_sla_sweep", queue="notifications")  # type: ignore[misc]
def approval_sla_sweep() -> int:
    """Daily beat: fire reminder/escalation for plans stuck in PENDING_APPROVAL (T-094)."""
    return run_db(_approval_sla_sweep)


async def _approval_sla_sweep(session: AsyncSession) -> int:
    from app.features.exam_frameworks.service import ExamFrameworkService

    svc = ExamFrameworkService(session)
    fired = await svc.sweep_approval_sla()
    logger.info("framework_approval_sla_sweep_complete", fired=fired)
    return fired


@shared_task(name="framework.refresh_quarterly", queue="ml")  # type: ignore[misc]
def refresh_quarterly() -> int:
    """Daily beat: re-research PUBLISHED frameworks past the refresh cadence (T-095).

    The 90-day cadence (``FRAMEWORK_REFRESH_DAYS``) is enforced in the service, not the
    beat — the beat wakes daily and lets the service pick what is due (ARCH §10.6).
    """
    return run_db(_refresh_quarterly)


async def _refresh_quarterly(session: AsyncSession) -> int:
    from app.features.exam_frameworks.service import ExamFrameworkService

    svc = ExamFrameworkService(session)
    triggered = await svc.sweep_quarterly_refresh()
    logger.info("framework_refresh_quarterly_complete", triggered=triggered)
    return triggered
