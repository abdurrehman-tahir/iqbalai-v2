"""Exam Framework service — Platform-Admin CRUD over framework definitions (T-092).

A framework definition is a thin metadata record (name, exam target, region, target
grade range, language) created at ``DRAFT`` by a Platform Admin (ARCH §3.19). Only
DRAFT definitions may be edited or deleted — once initial research runs (T-093) the
record leaves DRAFT and is managed through the research/approval/versioning workflow.
Delete is a soft-delete (SoftDeleteMixin), consistent with the house pattern.
"""

from __future__ import annotations

from datetime import datetime, timezone

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.exceptions import ConflictError, NotFoundError
from app.features.exam_frameworks import research
from app.features.exam_frameworks.models import (
    ExamFramework,
    FrameworkResearchJob,
    FrameworkStatus,
    FrameworkStudyPlan,
    ResearchJobStatus,
    StudyPlanStatus,
)
from app.features.exam_frameworks.repository import ExamFrameworkRepository
from app.features.exam_frameworks.schemas import (
    ExamFrameworkCreate,
    ExamFrameworkUpdate,
    FrameworkStudyPlanContent,
)

logger = structlog.get_logger(__name__)

# Transparency note attached to every AI-generated plan (ARCH §8.21 copyright rule).
COPYRIGHT_NOTE = (
    "Practice problems are AI-generated in the style of publicly available past "
    "papers, not reproductions of copyrighted questions. All sources are cited."
)


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

    # --- AI research run (T-093) ---------------------------------------------

    async def trigger_research(self, framework_id: str, actor_id: str) -> FrameworkResearchJob:
        """Kick off a Pattern-A research run for a DRAFT framework.

        Atomically moves the framework DRAFT -> RESEARCHING and records a RUNNING
        job, then enqueues the Celery task. Only DRAFT frameworks may be researched
        (re-triggering a failed run is allowed once it has reverted to DRAFT).
        """
        framework = await self.get_framework(framework_id)
        self._require_draft(framework, "researched")

        job = FrameworkResearchJob(
            framework_id=framework_id,
            status=ResearchJobStatus.RUNNING,
            started_at=datetime.now(timezone.utc),
        )
        framework.status = FrameworkStatus.RESEARCHING
        self._repo.add(job)
        await self._repo.commit()
        await self._repo.refresh(job)

        # Lazy import avoids a tasks<->service import cycle.
        from app.features.exam_frameworks.tasks import research_framework

        research_framework.delay(framework_id, job.id)
        logger.info(
            "framework_research_triggered",
            framework_id=framework_id,
            job_id=job.id,
            by=actor_id,
        )
        return job

    async def get_latest_job(self, framework_id: str) -> FrameworkResearchJob:
        """Return the most recent research job for a framework (404 if none)."""
        await self.get_framework(framework_id)
        job = await self._repo.get_latest_job(framework_id)
        if job is None:
            raise NotFoundError(f"No research job for framework '{framework_id}'")
        return job

    async def run_and_persist_research(self, framework_id: str, job_id: str) -> ResearchJobStatus:
        """Execute the research pipeline and persist the result (Celery task body).

        On success: writes a new PENDING_APPROVAL study-plan version, marks the job
        SUCCEEDED, and moves the framework to PENDING_APPROVAL. On a cost-ceiling
        halt: preserves the partial plan as DRAFT, marks the job PARTIAL, and reverts
        the framework to DRAFT. Hard failures raise (the task retries).
        """
        settings = get_settings()
        framework = await self._repo.get_by_id(framework_id)
        if framework is None:
            raise NotFoundError(f"Exam framework '{framework_id}' not found")
        job = await self._repo.get_job_by_id(job_id)
        if job is None:
            raise NotFoundError(f"Research job '{job_id}' not found")

        # Idempotency (§10.5 strategy 1): a finalised job is never re-run — this
        # prevents a retried task from producing a duplicate plan / double-charge.
        if job.status != ResearchJobStatus.RUNNING:
            logger.info(
                "framework_research_already_finalised", job_id=job_id, status=job.status.value
            )
            return job.status

        outcome = await research.run_research(
            framework,
            max_sources=settings.FRAMEWORK_RESEARCH_MAX_SOURCES,
            ceiling_usd=settings.FRAMEWORK_RESEARCH_COST_CEILING_USD,
            usd_per_1k=settings.FRAMEWORK_RESEARCH_USD_PER_1K_TOKENS,
        )

        version = await self._repo.next_plan_version(framework_id)
        now = datetime.now(timezone.utc)
        content = FrameworkStudyPlanContent(
            version=version,
            framework_name=framework.name,
            region=framework.region,
            target_grade_range=framework.target_grade_range,
            sources_cited=outcome.sources,
            generated_at=now.isoformat(),
            topics=outcome.topics,
            weekly_pacing=outcome.weekly_pacing,
            exam_strategy=outcome.exam_strategy,
            copyright_note=COPYRIGHT_NOTE,
        )
        # Partial (cost-halted) plans are preserved as DRAFT and not offered for
        # approval; complete plans go straight to PENDING_APPROVAL (T-094 gate).
        plan_status = StudyPlanStatus.DRAFT if outcome.partial else StudyPlanStatus.PENDING_APPROVAL
        plan = FrameworkStudyPlan(
            framework_id=framework_id,
            version=version,
            content_jsonb=content.model_dump(mode="json"),
            sources_cited_jsonb=[s.model_dump() for s in outcome.sources],
            generated_at=now,
            status=plan_status,
        )
        self._repo.add(plan)
        await self._repo.commit()
        await self._repo.refresh(plan)

        job.cost_usd = outcome.cost_usd
        job.sources_count = outcome.sources_count
        job.study_plan_id = plan.id
        job.finished_at = datetime.now(timezone.utc)
        if outcome.partial:
            job.status = ResearchJobStatus.PARTIAL
            job.error = "Cost ceiling reached; partial result preserved as a DRAFT plan."
            framework.status = FrameworkStatus.DRAFT
        else:
            job.status = ResearchJobStatus.SUCCEEDED
            framework.status = FrameworkStatus.PENDING_APPROVAL
        await self._repo.commit()

        logger.info(
            "framework_research_persisted",
            framework_id=framework_id,
            job_id=job_id,
            status=job.status.value,
            version=version,
            cost_usd=str(outcome.cost_usd),
        )
        return job.status

    async def mark_research_failed(self, framework_id: str, job_id: str, error: str) -> None:
        """Terminal failure after retries: flag the job, revert framework to DRAFT."""
        framework = await self._repo.get_by_id(framework_id)
        job = await self._repo.get_job_by_id(job_id)
        if job is not None:
            job.status = ResearchJobStatus.RESEARCH_FAILED
            job.error = error[:4000]
            job.finished_at = datetime.now(timezone.utc)
        if framework is not None and framework.status == FrameworkStatus.RESEARCHING:
            framework.status = FrameworkStatus.DRAFT
        await self._repo.commit()
        logger.warning(
            "framework_research_failed", framework_id=framework_id, job_id=job_id, error=error
        )
