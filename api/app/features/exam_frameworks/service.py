"""Exam Framework service — Platform-Admin CRUD over framework definitions (T-092).

A framework definition is a thin metadata record (name, exam target, region, target
grade range, language) created at ``DRAFT`` by a Platform Admin (ARCH §3.19). Only
DRAFT definitions may be edited or deleted — once initial research runs (T-093) the
record leaves DRAFT and is managed through the research/approval/versioning workflow.
Delete is a soft-delete (SoftDeleteMixin), consistent with the house pattern.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.exceptions import ConflictError, NotFoundError, PreconditionFailedError
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
from app.infrastructure.audit.log import audit

logger = structlog.get_logger(__name__)

# Transparency note attached to every AI-generated plan (ARCH §8.21 copyright rule).
COPYRIGHT_NOTE = (
    "Practice problems are AI-generated in the style of publicly available past "
    "papers, not reproductions of copyrighted questions. All sources are cited."
)


def _parse_sent_markers(raw: str | None) -> set[str]:
    """Parse the comma-separated SLA-reminder markers already fired for a plan."""
    if not raw:
        return set()
    return {part.strip() for part in raw.split(",") if part.strip()}


def _format_sent_markers(markers: set[str]) -> str | None:
    return ",".join(sorted(markers, key=int)) if markers else None


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
            # A refresh keeps its live version published; an initial run reverts to DRAFT.
            framework.status = await self._revert_status_after_research(framework_id)
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
        # A failed refresh keeps the live version published; an initial run reverts to
        # DRAFT (T-093/T-095). Only revert if research was actually in flight.
        if framework is not None and framework.status in (
            FrameworkStatus.RESEARCHING,
            FrameworkStatus.REFRESHING,
        ):
            framework.status = await self._revert_status_after_research(framework_id)
        await self._repo.commit()
        logger.warning(
            "framework_research_failed", framework_id=framework_id, job_id=job_id, error=error
        )

    # --- approval workflow (T-094) -------------------------------------------

    async def get_plan_for_review(self, framework_id: str) -> FrameworkStudyPlan:
        """The PENDING_APPROVAL plan a Platform Admin reviews before approving.

        404 if the framework isn't awaiting approval — students never reach here,
        and the caller (router) is already ``platform_admin``-gated.
        """
        framework = await self.get_framework(framework_id)
        if framework.status != FrameworkStatus.PENDING_APPROVAL:
            raise NotFoundError(
                f"Framework '{framework_id}' has no plan pending approval "
                f"(status '{framework.status.value}')"
            )
        plan = await self._repo.get_pending_plan(framework_id)
        if plan is None:
            raise NotFoundError(f"No pending study plan for framework '{framework_id}'")
        return plan

    async def approve_plan(self, framework_id: str, actor_id: str) -> FrameworkStudyPlan:
        """Approve the pending plan -> PUBLISHED (Acceptance #2).

        Supersedes the previously published version (if any) so exactly one plan is
        APPROVED at a time; the framework moves to PUBLISHED and becomes selectable.
        Approval is an elevated, audited action (§14.10) — it exposes content to
        students.
        """
        framework = await self.get_framework(framework_id)
        if framework.status != FrameworkStatus.PENDING_APPROVAL:
            raise ConflictError(
                f"Only a framework pending approval can be approved "
                f"(framework '{framework_id}' is '{framework.status.value}')"
            )
        plan = await self._repo.get_pending_plan(framework_id)
        if plan is None:
            raise PreconditionFailedError(
                f"No pending study plan to approve for framework '{framework_id}'"
            )

        # Retire the prior published version so only the newest is APPROVED (§4.18).
        prior = await self._repo.get_current_published_plan(framework_id)
        if prior is not None and prior.id != plan.id:
            prior.status = StudyPlanStatus.SUPERSEDED

        now = datetime.now(timezone.utc)
        plan.status = StudyPlanStatus.APPROVED
        plan.approved_by = actor_id
        plan.approved_at = now
        framework.status = FrameworkStatus.PUBLISHED
        await self._repo.commit()
        await self._repo.refresh(plan)

        await audit(
            session=self._session,
            action="framework.approved",
            actor_id=actor_id,
            actor_role="platform_admin",
            target_type="framework_study_plan",
            target_id=plan.id,
            metadata={"flagged": True, "framework_id": framework_id, "version": plan.version},
        )
        await audit(
            session=self._session,
            action="framework.published",
            actor_id=actor_id,
            actor_role="platform_admin",
            target_type="exam_framework",
            target_id=framework_id,
            metadata={"flagged": True, "version": plan.version},
        )
        logger.info(
            "framework_plan_approved",
            framework_id=framework_id,
            plan_id=plan.id,
            version=plan.version,
            by=actor_id,
        )
        return plan

    async def reject_plan(self, framework_id: str, notes: str, actor_id: str) -> FrameworkStudyPlan:
        """Reject the pending plan -> back to DRAFT with reviewer notes (Acceptance #3)."""
        framework = await self.get_framework(framework_id)
        if framework.status != FrameworkStatus.PENDING_APPROVAL:
            raise ConflictError(
                f"Only a framework pending approval can be rejected "
                f"(framework '{framework_id}' is '{framework.status.value}')"
            )
        plan = await self._repo.get_pending_plan(framework_id)
        if plan is None:
            raise PreconditionFailedError(
                f"No pending study plan to reject for framework '{framework_id}'"
            )

        plan.status = StudyPlanStatus.DRAFT
        plan.reviewer_notes = notes
        # Rejecting a refresh (v2) leaves the live v1 published; rejecting an initial
        # plan reverts the framework to DRAFT (T-094/T-095).
        framework.status = await self._revert_status_after_research(framework_id)
        await self._repo.commit()
        await self._repo.refresh(plan)

        await audit(
            session=self._session,
            action="framework.rejected",
            actor_id=actor_id,
            actor_role="platform_admin",
            target_type="framework_study_plan",
            target_id=plan.id,
            metadata={"framework_id": framework_id, "version": plan.version},
        )
        logger.info(
            "framework_plan_rejected",
            framework_id=framework_id,
            plan_id=plan.id,
            by=actor_id,
        )
        return plan

    async def sweep_approval_sla(self) -> int:
        """Fire reminder/escalation events for plans stuck in PENDING_APPROVAL.

        Reminder after ``FRAMEWORK_APPROVAL_REMINDER_DAYS`` (7); escalation after
        ``FRAMEWORK_APPROVAL_ESCALATION_DAYS`` (14). Each marker is recorded on the
        plan's ``sla_reminders_sent`` so it never re-fires (idempotent beat, T-094).
        Notification delivery is layered on in T-097; here we detect + audit.
        Returns the number of markers fired this sweep.
        """
        settings = get_settings()
        reminder_days = settings.FRAMEWORK_APPROVAL_REMINDER_DAYS
        escalation_days = settings.FRAMEWORK_APPROVAL_ESCALATION_DAYS
        now = datetime.now(timezone.utc)
        fired = 0

        for framework in await self._repo.list_pending_approval_frameworks():
            plan = await self._repo.get_pending_plan(framework.id)
            if plan is None:
                continue
            age_days = (now - plan.generated_at).days
            sent = _parse_sent_markers(plan.sla_reminders_sent)

            # Escalation supersedes the reminder once the harder threshold is crossed.
            marker: str | None = None
            action: str | None = None
            if age_days >= escalation_days and str(escalation_days) not in sent:
                marker, action = str(escalation_days), "framework.approval_escalated"
            elif age_days >= reminder_days and str(reminder_days) not in sent:
                marker, action = str(reminder_days), "framework.approval_reminder"
            if marker is None or action is None:
                continue

            sent.add(marker)
            plan.sla_reminders_sent = _format_sent_markers(sent)
            await self._repo.commit()
            await audit(
                session=self._session,
                action=action,
                actor_id="system",
                actor_role="system",
                target_type="exam_framework",
                target_id=framework.id,
                metadata={
                    "flagged": action == "framework.approval_escalated",
                    "plan_id": plan.id,
                    "age_days": age_days,
                },
            )
            fired += 1
            logger.info(
                "framework_approval_sla_fired",
                framework_id=framework.id,
                plan_id=plan.id,
                action=action,
                age_days=age_days,
            )
        return fired

    async def _revert_status_after_research(self, framework_id: str) -> FrameworkStatus:
        """Where a framework lands when a research run does not publish.

        PUBLISHED if a live approved version already exists (a *refresh* run keeps its
        current version live); DRAFT otherwise (the *initial* run has nothing to fall
        back to). Never auto-switches students — the live plan is untouched (T-095).
        """
        published = await self._repo.get_current_published_plan(framework_id)
        return FrameworkStatus.PUBLISHED if published is not None else FrameworkStatus.DRAFT

    # --- versioning + quarterly refresh + deprecation (T-095) -----------------

    async def list_plan_versions(self, framework_id: str) -> list[FrameworkStudyPlan]:
        """Full version history for a framework (newest first), for the review UI."""
        await self.get_framework(framework_id)
        return await self._repo.list_plans(framework_id)

    async def trigger_refresh(self, framework_id: str, actor_id: str) -> FrameworkResearchJob:
        """Re-run research on a PUBLISHED framework -> new version (Acceptance #1).

        Moves PUBLISHED -> REFRESHING and enqueues the same Pattern-A pipeline as the
        initial run; a success produces version n+1 in PENDING_APPROVAL for the same
        Platform-Admin approval gate. The live version stays published throughout — a
        refresh never disturbs pinned students until they opt in (T-096).
        """
        framework = await self.get_framework(framework_id)
        if framework.status != FrameworkStatus.PUBLISHED:
            raise ConflictError(
                f"Only a PUBLISHED framework can be refreshed "
                f"(framework '{framework_id}' is '{framework.status.value}')"
            )

        job = FrameworkResearchJob(
            framework_id=framework_id,
            status=ResearchJobStatus.RUNNING,
            started_at=datetime.now(timezone.utc),
        )
        framework.status = FrameworkStatus.REFRESHING
        self._repo.add(job)
        await self._repo.commit()
        await self._repo.refresh(job)

        # Lazy import avoids a tasks<->service import cycle.
        from app.features.exam_frameworks.tasks import research_framework

        research_framework.delay(framework_id, job.id)
        await audit(
            session=self._session,
            action="framework.refresh_triggered",
            actor_id=actor_id,
            actor_role="platform_admin",
            target_type="exam_framework",
            target_id=framework_id,
            metadata={"job_id": job.id},
        )
        logger.info("framework_refresh_triggered", framework_id=framework_id, job_id=job.id)
        return job

    async def sweep_quarterly_refresh(self) -> int:
        """Beat body: re-research each PUBLISHED framework past the refresh cadence.

        Runs daily; ``FRAMEWORK_REFRESH_DAYS`` (default 90) sets the cadence, checked
        against each framework's last research run (ARCH §8.21/§10.6). Returns the
        number of frameworks moved into a refresh this sweep.
        """
        settings = get_settings()
        cutoff = datetime.now(timezone.utc) - timedelta(days=settings.FRAMEWORK_REFRESH_DAYS)
        due = await self._repo.list_frameworks_due_for_refresh(cutoff)
        triggered = 0
        for framework in due:
            await self.trigger_refresh(framework.id, actor_id="system")
            triggered += 1
        logger.info("framework_quarterly_refresh_swept", due=len(due), triggered=triggered)
        return triggered

    async def deprecate_framework(self, framework_id: str, actor_id: str) -> ExamFramework:
        """Deprecate a PUBLISHED framework (Acceptance #4).

        No longer offered for new selections (T-096 filters DEPRECATED out); existing
        students are grandfathered — their selections and pinned versions are untouched.
        Elevated, audited action (§14.10) — it changes what students may select.
        """
        framework = await self.get_framework(framework_id)
        if framework.status != FrameworkStatus.PUBLISHED:
            raise ConflictError(
                f"Only a PUBLISHED framework can be deprecated "
                f"(framework '{framework_id}' is '{framework.status.value}')"
            )
        framework.status = FrameworkStatus.DEPRECATED
        await self._repo.commit()
        await self._repo.refresh_framework(framework)

        await audit(
            session=self._session,
            action="framework.deprecated",
            actor_id=actor_id,
            actor_role="platform_admin",
            target_type="exam_framework",
            target_id=framework_id,
            metadata={"flagged": True},
        )
        logger.info("framework_deprecated", framework_id=framework_id, by=actor_id)
        return framework
