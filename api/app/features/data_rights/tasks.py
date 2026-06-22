"""Async data export processing — T-084."""

from __future__ import annotations

import asyncio

import structlog
from celery import shared_task

logger = structlog.get_logger(__name__)


@shared_task(name="data_rights.process_export", queue="default")
def process_data_export(request_id: str) -> None:
    """Build and store a personal data export bundle."""
    asyncio.run(_process_data_export_async(request_id))


async def _process_data_export_async(request_id: str) -> None:
    from app.db.session import async_session_factory
    from app.features.data_rights.service import DataRightsService

    async with async_session_factory() as session:
        svc = DataRightsService(session)
        await svc.process_export_request(request_id)
    logger.info("data_export_task_complete", request_id=request_id)
