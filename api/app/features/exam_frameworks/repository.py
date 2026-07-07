"""Exam Framework repository — DB queries for framework definitions (T-092).

Frameworks are platform-tier (not school-scoped): every Platform Admin sees the
same catalogue, so there is no tenant/school filter here.
"""

from __future__ import annotations

from datetime import datetime, timezone

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import not_deleted
from app.features.exam_frameworks.models import (
    ExamFramework,
    FrameworkResearchJob,
    FrameworkStatus,
    FrameworkStudyPlan,
    StudyPlanStatus,
)

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

    # --- research jobs + study plans (T-093) ----------------------------------
    # These share the caller's transaction: ``add`` + ``commit`` let the service
    # persist a framework status change, a job, and a plan version atomically.

    def add(self, obj: FrameworkResearchJob | FrameworkStudyPlan) -> None:
        """Stage a new row on the session without committing (atomic multi-write)."""
        self._session.add(obj)

    async def get_plan_by_id(self, plan_id: str) -> FrameworkStudyPlan | None:
        result = await self._session.execute(
            select(FrameworkStudyPlan).where(FrameworkStudyPlan.id == plan_id)
        )
        return result.scalar_one_or_none()

    async def get_pending_plan(self, framework_id: str) -> FrameworkStudyPlan | None:
        """The latest PENDING_APPROVAL plan for a framework (the one under review)."""
        result = await self._session.execute(
            select(FrameworkStudyPlan)
            .where(
                FrameworkStudyPlan.framework_id == framework_id,
                FrameworkStudyPlan.status == StudyPlanStatus.PENDING_APPROVAL,
            )
            .order_by(FrameworkStudyPlan.version.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_current_published_plan(self, framework_id: str) -> FrameworkStudyPlan | None:
        """The current APPROVED plan (highest version) for a framework, if any."""
        result = await self._session.execute(
            select(FrameworkStudyPlan)
            .where(
                FrameworkStudyPlan.framework_id == framework_id,
                FrameworkStudyPlan.status == StudyPlanStatus.APPROVED,
            )
            .order_by(FrameworkStudyPlan.version.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_plan_by_version(
        self, framework_id: str, version: int
    ) -> FrameworkStudyPlan | None:
        result = await self._session.execute(
            select(FrameworkStudyPlan).where(
                FrameworkStudyPlan.framework_id == framework_id,
                FrameworkStudyPlan.version == version,
            )
        )
        return result.scalar_one_or_none()

    async def list_pending_approval_frameworks(self) -> list[ExamFramework]:
        """Frameworks awaiting Platform-Admin approval — for the SLA beat (T-094)."""
        result = await self._session.execute(
            select(ExamFramework).where(
                ExamFramework.status == FrameworkStatus.PENDING_APPROVAL,
                not_deleted(ExamFramework),
            )
        )
        return list(result.scalars().all())

    async def commit(self) -> None:
        await self._session.commit()

    async def refresh(self, obj: FrameworkResearchJob | FrameworkStudyPlan) -> None:
        await self._session.refresh(obj)

    async def get_job_by_id(self, job_id: str) -> FrameworkResearchJob | None:
        result = await self._session.execute(
            select(FrameworkResearchJob).where(FrameworkResearchJob.id == job_id)
        )
        return result.scalar_one_or_none()

    async def get_latest_job(self, framework_id: str) -> FrameworkResearchJob | None:
        """Most recently created research job for a framework, if any."""
        result = await self._session.execute(
            select(FrameworkResearchJob)
            .where(FrameworkResearchJob.framework_id == framework_id)
            .order_by(FrameworkResearchJob.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def next_plan_version(self, framework_id: str) -> int:
        """Next study-plan version number for a framework (1-based, append-only)."""
        result = await self._session.execute(
            select(func.max(FrameworkStudyPlan.version)).where(
                FrameworkStudyPlan.framework_id == framework_id
            )
        )
        current = result.scalar_one_or_none()
        return (current or 0) + 1
