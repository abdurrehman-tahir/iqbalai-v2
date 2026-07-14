"""Invite expiry sweep — fires account.invite_expired notifications (T-038)."""

from __future__ import annotations

import asyncio

import structlog
from celery import shared_task

logger = structlog.get_logger(__name__)


@shared_task(name="account.expire_stale_invites", queue="notifications")  # type: ignore[misc]
def expire_stale_invites() -> int:
    """Mark expired pending invites and notify inviting admins."""
    return asyncio.run(_expire_stale_invites_async())


async def _expire_stale_invites_async() -> int:
    from app.db.session import async_session_factory
    from app.features.invites.service import InviteService

    count = 0
    async with async_session_factory() as session:
        svc = InviteService(session)
        count = await svc.expire_stale_invites_and_notify()
    logger.info("expire_stale_invites_complete", expired_count=count)
    return count
