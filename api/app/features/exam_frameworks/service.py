"""Exam Framework service — Platform-Admin CRUD over framework definitions (T-092).

A framework definition is a thin metadata record (name, exam target, region, target
grade range, language) created at ``DRAFT`` by a Platform Admin (ARCH §3.19). Only
DRAFT definitions may be edited or deleted — once initial research runs (T-093) the
record leaves DRAFT and is managed through the research/approval/versioning workflow.
Delete is a soft-delete (SoftDeleteMixin), consistent with the house pattern.
"""

from __future__ import annotations

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.features.exam_frameworks.models import ExamFramework, FrameworkStatus
from app.features.exam_frameworks.repository import ExamFrameworkRepository
from app.features.exam_frameworks.schemas import ExamFrameworkCreate, ExamFrameworkUpdate

logger = structlog.get_logger(__name__)


class ExamFrameworkService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = ExamFrameworkRepository(session)

    async def list_frameworks(
        self,
        status: FrameworkStatus | None = None,
        include_deleted: bool = False,
    ) -> list[ExamFramework]:
        return await self._repo.list_frameworks(status=status, include_deleted=include_deleted)

    async def get_framework(self, id: str) -> ExamFramework:
        framework = await self._repo.get_by_id(id)
        if framework is None or framework.deleted_at is not None:
            raise NotFoundError(f"Exam framework '{id}' not found")
        return framework

    async def create_framework(self, payload: ExamFrameworkCreate, actor_id: str) -> ExamFramework:
        framework = ExamFramework(
            name=payload.name,
            exam_target=payload.exam_target,
            region=payload.region,
            target_grade_range=payload.target_grade_range,
            language=payload.language,
            status=FrameworkStatus.DRAFT,
            created_by=actor_id,
        )
        created = await self._repo.create(framework)
        logger.info("exam_framework_created", framework_id=created.id, by=actor_id)
        return created

    async def update_framework(
        self, id: str, payload: ExamFrameworkUpdate, actor_id: str
    ) -> ExamFramework:
        framework = await self.get_framework(id)
        self._require_draft(framework, "edited")

        if payload.name is not None:
            framework.name = payload.name
        if payload.exam_target is not None:
            framework.exam_target = payload.exam_target
        if payload.region is not None:
            framework.region = payload.region
        if payload.target_grade_range is not None:
            framework.target_grade_range = payload.target_grade_range
        if payload.language is not None:
            framework.language = payload.language

        updated = await self._repo.update(framework)
        logger.info("exam_framework_updated", framework_id=updated.id, by=actor_id)
        return updated

    async def delete_framework(self, id: str, actor_id: str) -> ExamFramework:
        framework = await self.get_framework(id)
        self._require_draft(framework, "deleted")
        await self._repo.soft_delete(framework)
        logger.info("exam_framework_deleted", framework_id=framework.id, by=actor_id)
        return framework

    @staticmethod
    def _require_draft(framework: ExamFramework, verb: str) -> None:
        """Guard: only DRAFT definitions can be edited/deleted (Acceptance #3)."""
        if framework.status != FrameworkStatus.DRAFT:
            raise ConflictError(
                f"Only DRAFT frameworks can be {verb} "
                f"(framework '{framework.id}' is '{framework.status.value}')"
            )
