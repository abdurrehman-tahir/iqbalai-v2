"""Unlinked parent auto-suspend sweep — flow-4 §3.3 / T-080."""

from __future__ import annotations

import asyncio

import structlog
from celery import shared_task

logger = structlog.get_logger(__name__)


@shared_task(name="unlinked_parent.auto_suspend_sweep", queue="notifications")  # type: ignore[misc]
def auto_suspend_unlinked_parents() -> int:
    """Suspend parents who remain unlinked for 90+ days."""
    return asyncio.run(_auto_suspend_unlinked_parents_async())


async def _auto_suspend_unlinked_parents_async() -> int:
    from app.db.session import async_session_factory
    from app.features.parent_signup.service import ParentSignupService

    count = 0
    async with async_session_factory() as session:
        svc = ParentSignupService(session)
        count = await svc.suspend_stale_unlinked_parents()
    logger.info("auto_suspend_unlinked_parents_complete", suspended_count=count)
    return count
