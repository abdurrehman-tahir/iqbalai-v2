"""Exam Framework repository — DB queries for framework definitions (T-092).

Frameworks are platform-tier (not school-scoped): every Platform Admin sees the
same catalogue, so there is no tenant/school filter here.
"""

from __future__ import annotations

from datetime import datetime, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import not_deleted
from app.features.exam_frameworks.models import ExamFramework, FrameworkStatus

logger = structlog.get_logger(__name__)


class ExamFrameworkRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_frameworks(
        self,
        status: FrameworkStatus | None = None,
        include_deleted: bool = False,
    ) -> list[ExamFramework]:
        """List framework definitions, newest first; optionally filter by status."""
        stmt = select(ExamFramework)
        if not include_deleted:
            stmt = stmt.where(not_deleted(ExamFramework))
        if status is not None:
            stmt = stmt.where(ExamFramework.status == status)
        stmt = stmt.order_by(ExamFramework.created_at.desc())
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_id(self, id: str) -> ExamFramework | None:
        result = await self._session.execute(select(ExamFramework).where(ExamFramework.id == id))
        return result.scalar_one_or_none()

    async def create(self, framework: ExamFramework) -> ExamFramework:
        self._session.add(framework)
        await self._session.commit()
        await self._session.refresh(framework)
        return framework

    async def update(self, framework: ExamFramework) -> ExamFramework:
        await self._session.commit()
        await self._session.refresh(framework)
        return framework

    async def soft_delete(self, framework: ExamFramework) -> None:
        framework.deleted_at = datetime.now(timezone.utc)
        await self._session.commit()
