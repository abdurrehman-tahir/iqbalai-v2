"""Service + endpoint tests for the research run — T-093.

Covers ``trigger_research`` (DRAFT->RESEARCHING + RUNNING job + task enqueue),
``run_and_persist_research`` (success->PENDING_APPROVAL plan; partial->DRAFT plan;
idempotency guard), ``mark_research_failed``, and the two HTTP routes (202 trigger,
403 for non-Platform-Admin, latest-job fetch). The repo + research pipeline are
faked in-memory so the tests stay at the orchestration layer.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.v1.router import router as v1_router
from app.core.dependencies import get_current_user, get_db
from app.core.exceptions import setup_exception_handlers
from app.features.exam_frameworks import service as service_module
from app.features.exam_frameworks.models import (
    ExamFramework,
    FrameworkResearchJob,
    FrameworkStatus,
    FrameworkStudyPlan,
    ResearchJobStatus,
    StudyPlanStatus,
)
from app.features.exam_frameworks.research import ResearchOutcome
from app.features.exam_frameworks.schemas import ExamStrategy, FrameworkTopic, WeeklyPacing
from app.features.exam_frameworks.service import ExamFrameworkService


class _FakeRepo:
    """In-memory stand-in sharing dicts across instances (one logical session)."""

    frameworks: dict[str, ExamFramework] = {}
    jobs: dict[str, FrameworkResearchJob] = {}
    plans: dict[str, FrameworkStudyPlan] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def get_by_id(self, id: str) -> ExamFramework | None:
        return self.frameworks.get(id)

    def add(self, obj: Any) -> None:
        now = datetime.now(timezone.utc)
        if isinstance(obj, FrameworkResearchJob):
            obj.created_at = now
            obj.updated_at = now
            self.jobs[obj.id] = obj
        elif isinstance(obj, FrameworkStudyPlan):
            obj.created_at = now
            obj.updated_at = now
            self.plans[obj.id] = obj

    async def commit(self) -> None:
        return None

    async def refresh(self, obj: Any) -> None:
        return None

    async def get_current_published_plan(self, framework_id: str) -> FrameworkStudyPlan | None:
        appr = [
            p
            for p in self.plans.values()
            if p.framework_id == framework_id and p.status == StudyPlanStatus.APPROVED
        ]
        return max(appr, key=lambda p: p.version) if appr else None

    async def get_job_by_id(self, job_id: str) -> FrameworkResearchJob | None:
        return self.jobs.get(job_id)

    async def get_latest_job(self, framework_id: str) -> FrameworkResearchJob | None:
        rows = [j for j in self.jobs.values() if j.framework_id == framework_id]
        return sorted(rows, key=lambda j: j.created_at)[-1] if rows else None

    async def next_plan_version(self, framework_id: str) -> int:
        versions = [p.version for p in self.plans.values() if p.framework_id == framework_id]
        return (max(versions) if versions else 0) + 1


def _framework(status: FrameworkStatus = FrameworkStatus.DRAFT) -> ExamFramework:
    fw = ExamFramework(
        id="fw-1",
        name="Matric Punjab — Physics",
        exam_target="Matric Punjab Board — Physics",
        region="Punjab",
        target_grade_range=[9, 10],
        language="en",
        status=status,
        created_by="admin-1",
    )
    fw.created_at = datetime.now(timezone.utc)
    fw.updated_at = datetime.now(timezone.utc)
    return fw


def _outcome(partial: bool = False) -> ResearchOutcome:
    return ResearchOutcome(
        partial=partial,
        topics=[
            FrameworkTopic(
                topic_name="Kinematics",
                priority_weight=0.9,
                exam_frequency="every_year",
                recommended_hours=12,
            )
        ],
        weekly_pacing=[
            WeeklyPacing(week_from_exam=8, focus_topics=["Kinematics"], hours_estimated=10)
        ],
        exam_strategy=ExamStrategy(),
        sources=[],
        cost_usd=Decimal("1.5"),
    )


@pytest.fixture(autouse=True)
def _reset_repo(monkeypatch: pytest.MonkeyPatch) -> None:
    _FakeRepo.frameworks = {}
    _FakeRepo.jobs = {}
    _FakeRepo.plans = {}
    monkeypatch.setattr(service_module, "ExamFrameworkRepository", _FakeRepo)


@pytest.mark.asyncio
async def test_trigger_research_moves_to_researching(monkeypatch: pytest.MonkeyPatch) -> None:
    _FakeRepo.frameworks = {"fw-1": _framework()}
    enqueued: dict[str, Any] = {}

    class _FakeTask:
        @staticmethod
        def delay(framework_id: str, job_id: str) -> None:
            enqueued["framework_id"] = framework_id
            enqueued["job_id"] = job_id

    # trigger_research lazy-imports the task from tasks module.
    monkeypatch.setattr(
        "app.features.exam_frameworks.tasks.research_framework", _FakeTask, raising=False
    )

    svc = ExamFrameworkService(session=None)  # type: ignore[arg-type]
    job = await svc.trigger_research("fw-1", actor_id="admin-1")

    assert job.status == ResearchJobStatus.RUNNING
    assert _FakeRepo.frameworks["fw-1"].status == FrameworkStatus.RESEARCHING
    assert enqueued["framework_id"] == "fw-1"
    assert enqueued["job_id"] == job.id


@pytest.mark.asyncio
async def test_trigger_research_non_draft_conflicts() -> None:
    _FakeRepo.frameworks = {"fw-1": _framework(status=FrameworkStatus.PUBLISHED)}
    svc = ExamFrameworkService(session=None)  # type: ignore[arg-type]
    from app.core.exceptions import ConflictError

    with pytest.raises(ConflictError):
        await svc.trigger_research("fw-1", actor_id="admin-1")


@pytest.mark.asyncio
async def test_run_and_persist_success(monkeypatch: pytest.MonkeyPatch) -> None:
    _FakeRepo.frameworks = {"fw-1": _framework(status=FrameworkStatus.RESEARCHING)}
    job = FrameworkResearchJob(
        id="job-1", framework_id="fw-1", started_at=datetime.now(timezone.utc)
    )
    job.created_at = datetime.now(timezone.utc)
    _FakeRepo.jobs = {"job-1": job}

    async def _fake_run(*args: Any, **kwargs: Any) -> ResearchOutcome:
        return _outcome(partial=False)

    monkeypatch.setattr("app.features.exam_frameworks.research.run_research", _fake_run)

    svc = ExamFrameworkService(session=None)  # type: ignore[arg-type]
    status = await svc.run_and_persist_research("fw-1", "job-1")

    assert status == ResearchJobStatus.SUCCEEDED
    assert _FakeRepo.frameworks["fw-1"].status == FrameworkStatus.PENDING_APPROVAL
    plan = next(iter(_FakeRepo.plans.values()))
    assert plan.status == StudyPlanStatus.PENDING_APPROVAL
    assert plan.version == 1
    assert job.study_plan_id == plan.id


@pytest.mark.asyncio
async def test_run_and_persist_partial_keeps_draft(monkeypatch: pytest.MonkeyPatch) -> None:
    _FakeRepo.frameworks = {"fw-1": _framework(status=FrameworkStatus.RESEARCHING)}
    job = FrameworkResearchJob(
        id="job-1", framework_id="fw-1", started_at=datetime.now(timezone.utc)
    )
    job.created_at = datetime.now(timezone.utc)
    _FakeRepo.jobs = {"job-1": job}

    async def _fake_run(*args: Any, **kwargs: Any) -> ResearchOutcome:
        return _outcome(partial=True)

    monkeypatch.setattr("app.features.exam_frameworks.research.run_research", _fake_run)

    svc = ExamFrameworkService(session=None)  # type: ignore[arg-type]
    status = await svc.run_and_persist_research("fw-1", "job-1")

    assert status == ResearchJobStatus.PARTIAL
    # A cost-halted run reverts the framework to DRAFT and preserves a DRAFT plan.
    assert _FakeRepo.frameworks["fw-1"].status == FrameworkStatus.DRAFT
    plan = next(iter(_FakeRepo.plans.values()))
    assert plan.status == StudyPlanStatus.DRAFT


@pytest.mark.asyncio
async def test_run_and_persist_is_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    _FakeRepo.frameworks = {"fw-1": _framework(status=FrameworkStatus.PENDING_APPROVAL)}
    job = FrameworkResearchJob(
        id="job-1",
        framework_id="fw-1",
        status=ResearchJobStatus.SUCCEEDED,
        started_at=datetime.now(timezone.utc),
    )
    job.created_at = datetime.now(timezone.utc)
    _FakeRepo.jobs = {"job-1": job}

    called = {"n": 0}

    async def _fake_run(*args: Any, **kwargs: Any) -> ResearchOutcome:
        called["n"] += 1
        return _outcome()

    monkeypatch.setattr("app.features.exam_frameworks.research.run_research", _fake_run)

    svc = ExamFrameworkService(session=None)  # type: ignore[arg-type]
    status = await svc.run_and_persist_research("fw-1", "job-1")

    # A finalised job is never re-run -> no pipeline call, no duplicate plan.
    assert status == ResearchJobStatus.SUCCEEDED
    assert called["n"] == 0
    assert _FakeRepo.plans == {}


@pytest.mark.asyncio
async def test_mark_research_failed_reverts_draft() -> None:
    _FakeRepo.frameworks = {"fw-1": _framework(status=FrameworkStatus.RESEARCHING)}
    job = FrameworkResearchJob(
        id="job-1", framework_id="fw-1", started_at=datetime.now(timezone.utc)
    )
    _FakeRepo.jobs = {"job-1": job}

    svc = ExamFrameworkService(session=None)  # type: ignore[arg-type]
    await svc.mark_research_failed("fw-1", "job-1", "boom")

    assert job.status == ResearchJobStatus.RESEARCH_FAILED
    assert job.error == "boom"
    assert _FakeRepo.frameworks["fw-1"].status == FrameworkStatus.DRAFT


# --- HTTP routes -----------------------------------------------------------


def _build_client(role: str = "platform_admin") -> AsyncClient:
    app = FastAPI()
    app.include_router(v1_router, prefix="/api/v1")
    setup_exception_handlers(app)

    async def _override_db() -> AsyncGenerator[None, None]:
        yield None

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = lambda: {"sub": "admin-1", "role": role}
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_trigger_endpoint_returns_202(monkeypatch: pytest.MonkeyPatch) -> None:
    _FakeRepo.frameworks = {"fw-1": _framework()}

    class _FakeTask:
        @staticmethod
        def delay(framework_id: str, job_id: str) -> None:
            return None

    monkeypatch.setattr(
        "app.features.exam_frameworks.tasks.research_framework", _FakeTask, raising=False
    )

    async with _build_client() as client:
        resp = await client.post("/api/v1/exam-frameworks/fw-1/research")

    assert resp.status_code == 202
    assert resp.json()["data"]["status"] == "running"


@pytest.mark.asyncio
async def test_trigger_endpoint_forbidden_for_non_admin() -> None:
    _FakeRepo.frameworks = {"fw-1": _framework()}
    async with _build_client(role="teacher") as client:
        resp = await client.post("/api/v1/exam-frameworks/fw-1/research")

    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_latest_job_endpoint_returns_job() -> None:
    _FakeRepo.frameworks = {"fw-1": _framework(status=FrameworkStatus.RESEARCHING)}
    job = FrameworkResearchJob(
        id="job-1", framework_id="fw-1", started_at=datetime.now(timezone.utc)
    )
    job.created_at = datetime.now(timezone.utc)
    _FakeRepo.jobs = {"job-1": job}

    async with _build_client() as client:
        resp = await client.get("/api/v1/exam-frameworks/fw-1/research")

    assert resp.status_code == 200
    assert resp.json()["data"]["id"] == "job-1"


@pytest.mark.asyncio
async def test_latest_job_endpoint_404_when_none() -> None:
    _FakeRepo.frameworks = {"fw-1": _framework()}
    async with _build_client() as client:
        resp = await client.get("/api/v1/exam-frameworks/fw-1/research")

    assert resp.status_code == 404
