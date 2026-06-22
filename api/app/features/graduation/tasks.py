"""Graduation Celery tasks — T-086."""

from __future__ import annotations

import asyncio

import structlog
from celery import shared_task

logger = structlog.get_logger(__name__)


@shared_task(name="graduation.migrate_eligible_students", queue="default")
def migrate_eligible_students() -> int:
    """Auto-migrate students past the graduation grace window."""
    return asyncio.run(_migrate_eligible_students_async())


@shared_task(name="graduation.migration_reminder_sweep", queue="notifications")
def migration_reminder_sweep() -> int:
    """Send 30/7-day pre-migration reminders."""
    return asyncio.run(_migration_reminder_sweep_async())


async def _migrate_eligible_students_async() -> int:
    from app.db.session import async_session_factory
    from app.features.graduation.service import GraduationService

    count = 0
    async with async_session_factory() as session:
        svc = GraduationService(session)
        count = await svc.migrate_eligible_students()
    logger.info("graduation_migration_sweep_complete", migrated_count=count)
    return count


async def _migration_reminder_sweep_async() -> int:
    from app.db.session import async_session_factory
    from app.features.graduation.service import GraduationService

    count = 0
    async with async_session_factory() as session:
        svc = GraduationService(session)
        count = await svc.send_migration_reminders()
    logger.info("graduation_reminder_sweep_complete", reminder_count=count)
    return count
