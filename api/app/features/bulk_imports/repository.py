"""Bulk import repository — T-037."""

from __future__ import annotations

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.bulk_imports.models import BulkImport

logger = structlog.get_logger(__name__)


class BulkImportRepository:
    """Data access for bulk import jobs."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, job: BulkImport) -> BulkImport:
        self._session.add(job)
        await self._session.commit()
        await self._session.refresh(job)
        return job

    async def get_by_id(self, import_id: str) -> BulkImport | None:
        result = await self._session.execute(select(BulkImport).where(BulkImport.id == import_id))
        return result.scalar_one_or_none()

    async def get_by_id_for_school(self, import_id: str, school_id: str) -> BulkImport | None:
        result = await self._session.execute(
            select(BulkImport).where(
                BulkImport.id == import_id,
                BulkImport.school_id == school_id,
            )
        )
        return result.scalar_one_or_none()

    async def update(self, job: BulkImport) -> BulkImport:
        await self._session.commit()
        await self._session.refresh(job)
        return job
