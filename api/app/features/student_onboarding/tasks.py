"""Exam countdown notification sweep — T-083."""

from __future__ import annotations

import asyncio

import structlog
from celery import shared_task

logger = structlog.get_logger(__name__)


@shared_task(name="self_study.exam_countdown_sweep", queue="notifications")
def exam_countdown_sweep() -> int:
    """Send 30/14/7/1-day exam countdown notifications to school students."""
    return asyncio.run(_exam_countdown_sweep_async())


async def _exam_countdown_sweep_async() -> int:
    from app.db.session import async_session_factory
    from app.features.student_onboarding.service import StudentOnboardingService

    count = 0
    async with async_session_factory() as session:
        svc = StudentOnboardingService(session)
        count = await svc.send_exam_countdown_notifications()
    logger.info("exam_countdown_sweep_complete", notification_count=count)
    return count
