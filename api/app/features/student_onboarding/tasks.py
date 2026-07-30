"""Exam countdown + diagnostic retake notification sweeps — T-083 / T-107 / T-109."""

from __future__ import annotations

import structlog
from celery import shared_task
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.celery_async import run_db

logger = structlog.get_logger(__name__)


@shared_task(name="self_study.exam_countdown_sweep", queue="notifications")  # type: ignore[misc]
def exam_countdown_sweep() -> int:
    """Send countdown + exam-passed notifications (school + independent)."""
    return run_db(_exam_countdown_sweep_async)


async def _exam_countdown_sweep_async(session: AsyncSession) -> int:
    from app.features.independent_student_onboarding.service import (
        IndependentStudentOnboardingService,
    )
    from app.features.student_onboarding.service import StudentOnboardingService

    school = await StudentOnboardingService(session).send_exam_countdown_notifications()
    independent = await IndependentStudentOnboardingService(
        session
    ).send_exam_countdown_notifications()
    total = school + independent
    logger.info(
        "exam_countdown_sweep_complete",
        school_notification_count=school,
        independent_notification_count=independent,
        notification_count=total,
    )
    return total


@shared_task(name="self_study.diagnostic_retake_sweep", queue="notifications")  # type: ignore[misc]
def diagnostic_retake_sweep() -> int:
    """Notify students when the 30-day diagnostic retake window opens (T-109)."""
    return run_db(_diagnostic_retake_sweep_async)


async def _diagnostic_retake_sweep_async(session: AsyncSession) -> int:
    from app.features.diagnostics.service import DiagnosticService

    school = await DiagnosticService(session, "school").send_retake_available_notifications()
    independent = await DiagnosticService(
        session, "independent"
    ).send_retake_available_notifications()
    total = school + independent
    logger.info(
        "diagnostic_retake_sweep_complete",
        school_notification_count=school,
        independent_notification_count=independent,
        notification_count=total,
    )
    return total
