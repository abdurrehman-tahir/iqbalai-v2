"""District repository — all DB queries for districts (T-029).

Districts are tenant-root tables with no RLS (ARCH §3.3); access is gated by role at
the router/service layer, not by row-level security. Soft-delete is filtered out by
default on reads.
"""

from __future__ import annotations

from datetime import datetime, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.schools.models import District

logger = structlog.get_logger(__name__)


class DistrictRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_districts(self) -> list[District]:
        """Return all active (non-deleted) districts, newest first."""
        result = await self._session.execute(
            select(District)
            .where(District.deleted_at.is_(None))
            .order_by(District.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_by_id(self, id: str) -> District | None:
        result = await self._session.execute(select(District).where(District.id == id))
        return result.scalar_one_or_none()

    async def get_active_by_name(self, name: str) -> District | None:
        """Return a non-deleted district with this exact name, if any."""
        result = await self._session.execute(
            select(District).where(District.name == name, District.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()

    async def create(self, district: District) -> District:
        self._session.add(district)
        await self._session.commit()
        await self._session.refresh(district)
        return district

    async def update(self, district: District) -> District:
        await self._session.commit()
        await self._session.refresh(district)
        return district

    async def soft_delete(self, district: District) -> None:
        district.deleted_at = datetime.now(timezone.utc)
        await self._session.commit()
