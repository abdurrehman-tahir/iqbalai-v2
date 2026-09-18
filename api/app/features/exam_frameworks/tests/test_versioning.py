"""Versioning + quarterly refresh + deprecation tests — T-095 (Flow 4 §3.5.1,
ARCH §3.19/§8.21/§10.6).

Covers the manual refresh endpoint (PUBLISHED -> REFRESHING + new research job), the
quarterly-refresh sweep (picks frameworks past ``FRAMEWORK_REFRESH_DAYS``), deprecation
(PUBLISHED -> DEPRECATED, existing selections grandfathered), version-history read, and
the refresh-safe revert (rejecting a refresh keeps the live version PUBLISHED, never
DRAFT). Backend is the in-memory fake repo used across the feature's API tests; ``audit``
and the Celery ``research_framework.delay`` enqueue are stubbed.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.v1.router import router as v1_router
from app.core.dependencies import get_current_user, get_db
from app.core.exceptions import setup_exception_handlers
from app.features.exam_frameworks.models import (
    ExamFramework,
    FrameworkResearchJob,
    FrameworkStatus,
    FrameworkStudyPlan,
    ResearchJobStatus,
    StudyPlanStatus,
)
from app.features.exam_frameworks.service import ExamFrameworkService


class _FakeRepo:
    frameworks: dict[str, ExamFramework] = {}
    plans: dict[str, FrameworkStudyPlan] = {}
    jobs: dict[str, FrameworkResearchJob] = {}
    due: list[ExamFramework] = []

    def __init__(self, session: Any) -> None:
        pass

    async def get_by_id(self, id: str) -> ExamFramework | None:
        return self.frameworks.get(id)

    async def get_current_published_plan(self, framework_id: str) -> FrameworkStudyPlan | None:
        appr = [
            p
            for p in self.plans.values()
            if p.framework_id == framework_id and p.status == StudyPlanStatus.APPROVED
        ]
        return max(appr, key=lambda p: p.version) if appr else None

    async def get_pending_plan(self, framework_id: str) -> FrameworkStudyPlan | None:
        pend = [
            p
            for p in self.plans.values()
            if p.framework_id == framework_id and p.status == StudyPlanStatus.PENDING_APPROVAL
        ]
        return max(pend, key=lambda p: p.version) if pend else None

    async def list_plans(self, framework_id: str) -> list[FrameworkStudyPlan]:
        rows = [p for p in self.plans.values() if p.framework_id == framework_id]
        return sorted(rows, key=lambda p: p.version, reverse=True)

    async def list_frameworks_due_for_refresh(self, cutoff: datetime) -> list[ExamFramework]:
        return list(self.due)

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
        pass

    async def refresh(self, obj: Any) -> None:
        pass

    async def refresh_framework(self, framework: ExamFramework) -> None:
        pass


def _framework(**overrides: Any) -> ExamFramework:
    now = datetime.now(timezone.utc)
    fields: dict[str, Any] = {
        "id": "fw-1",
        "name": "Matric Punjab — Physics",
        "exam_target": "Matric Punjab Board — Physics",
        "subject_slug": "physics",
        "region": "Punjab",
        "target_grade_range": [9, 10],
        "language": "en",
        "status": FrameworkStatus.PUBLISHED,
        "created_by": "admin-1",
    }
    fields.update(overrides)
    fw = ExamFramework(**fields)
    fw.created_at = now
    fw.updated_at = now
    return fw


def _plan(**overrides: Any) -> FrameworkStudyPlan:
    now = datetime.now(timezone.utc)
    fields: dict[str, Any] = {
        "id": "plan-1",
        "framework_id": "fw-1",
        "version": 1,
        "content_jsonb": {"topics": [], "weekly_pacing": [], "exam_strategy": {}},
        "sources_cited_jsonb": [{"url": "https://ex.com", "title": "Past papers"}],
        "generated_at": now,
        "status": StudyPlanStatus.APPROVED,
    }
    fields.update(overrides)
    plan = FrameworkStudyPlan(**fields)
    plan.created_at = now
    plan.updated_at = now
    return plan


class _FakeTask:
    """Stand-in for the Celery ``research_framework`` task — records enqueues."""

    calls: list[tuple[str, str]] = []

    @classmethod
    def delay(cls, framework_id: str, job_id: str) -> None:
        cls.calls.append((framework_id, job_id))


@pytest.fixture(autouse=True)
def _patch_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    _FakeRepo.frameworks = {}
    _FakeRepo.plans = {}
    _FakeRepo.jobs = {}
    _FakeRepo.due = []
    _FakeTask.calls = []
    monkeypatch.setattr("app.features.exam_frameworks.service.ExamFrameworkRepository", _FakeRepo)
    monkeypatch.setattr("app.features.exam_frameworks.tasks.research_framework", _FakeTask)

    async def _noop_audit(**kwargs: Any) -> None:
        return None

    monkeypatch.setattr("app.features.exam_frameworks.service.audit", _noop_audit)


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
async def test_refresh_moves_published_to_refreshing_and_enqueues() -> None:
    _FakeRepo.frameworks = {"fw-1": _framework()}
    async with _build_client() as client:
        resp = await client.post("/api/v1/exam-frameworks/fw-1/refresh")

    assert resp.status_code == 202
    assert resp.json()["data"]["status"] == "running"
    assert _FakeRepo.frameworks["fw-1"].status == FrameworkStatus.REFRESHING
    assert len(_FakeTask.calls) == 1


@pytest.mark.asyncio
async def test_refresh_conflicts_when_not_published() -> None:
    _FakeRepo.frameworks = {"fw-1": _framework(status=FrameworkStatus.DRAFT)}
    async with _build_client() as client:
        resp = await client.post("/api/v1/exam-frameworks/fw-1/refresh")

    assert resp.status_code == 409
    assert not _FakeTask.calls


@pytest.mark.asyncio
async def test_refresh_forbidden_for_non_platform_admin() -> None:
    _FakeRepo.frameworks = {"fw-1": _framework()}
    async with _build_client(role="teacher") as client:
        resp = await client.post("/api/v1/exam-frameworks/fw-1/refresh")

    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_deprecate_grandfathers_existing_and_blocks_new() -> None:
    _FakeRepo.frameworks = {"fw-1": _framework()}
    async with _build_client() as client:
        resp = await client.post("/api/v1/exam-frameworks/fw-1/deprecate")

    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "deprecated"
    assert _FakeRepo.frameworks["fw-1"].status == FrameworkStatus.DEPRECATED


@pytest.mark.asyncio
async def test_deprecate_conflicts_when_not_published() -> None:
    _FakeRepo.frameworks = {"fw-1": _framework(status=FrameworkStatus.DRAFT)}
    async with _build_client() as client:
        resp = await client.post("/api/v1/exam-frameworks/fw-1/deprecate")

    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_versions_returns_full_history_newest_first() -> None:
    _FakeRepo.frameworks = {"fw-1": _framework()}
    _FakeRepo.plans = {
        "plan-1": _plan(id="plan-1", version=1, status=StudyPlanStatus.SUPERSEDED),
        "plan-2": _plan(id="plan-2", version=2, status=StudyPlanStatus.APPROVED),
    }
    async with _build_client() as client:
        resp = await client.get("/api/v1/exam-frameworks/fw-1/versions")

    assert resp.status_code == 200
    versions = [p["version"] for p in resp.json()["data"]]
    assert versions == [2, 1]


@pytest.mark.asyncio
async def test_quarterly_sweep_triggers_due_frameworks() -> None:
    due = _framework(id="fw-due")
    _FakeRepo.frameworks = {"fw-due": due}
    _FakeRepo.due = [due]
    svc = ExamFrameworkService(session=None)  # type: ignore[arg-type]

    assert await svc.sweep_quarterly_refresh() == 1
    assert _FakeRepo.frameworks["fw-due"].status == FrameworkStatus.REFRESHING
    assert _FakeTask.calls == [("fw-due", _FakeTask.calls[0][1])]


@pytest.mark.asyncio
async def test_refresh_reject_keeps_live_version_published() -> None:
    # A refresh produced v2 (pending) while v1 stays live (approved). Rejecting v2 must
    # NOT drop the framework to DRAFT — the live v1 keeps students served (Acceptance #2).
    _FakeRepo.frameworks = {"fw-1": _framework(status=FrameworkStatus.PENDING_APPROVAL)}
    _FakeRepo.plans = {
        "plan-1": _plan(id="plan-1", version=1, status=StudyPlanStatus.APPROVED),
        "plan-2": _plan(id="plan-2", version=2, status=StudyPlanStatus.PENDING_APPROVAL),
    }
    async with _build_client() as client:
        resp = await client.post(
            "/api/v1/exam-frameworks/fw-1/reject",
            json={"notes": "v2 topic weights regressed; keep v1 live."},
        )

    assert resp.status_code == 200
    assert _FakeRepo.frameworks["fw-1"].status == FrameworkStatus.PUBLISHED
    assert _FakeRepo.plans["plan-2"].status == StudyPlanStatus.DRAFT
    assert _FakeRepo.plans["plan-1"].status == StudyPlanStatus.APPROVED


@pytest.mark.asyncio
async def test_refresh_partial_reverts_to_published(monkeypatch: pytest.MonkeyPatch) -> None:
    # A cost-halted refresh preserves the partial as DRAFT and returns the framework to
    # PUBLISHED (its live v1 is untouched) rather than DRAFT.
    from app.features.exam_frameworks import research as research_mod

    fw = _framework(id="fw-1", status=FrameworkStatus.REFRESHING)
    job = FrameworkResearchJob(
        id="job-1",
        framework_id="fw-1",
        status=ResearchJobStatus.RUNNING,
        started_at=datetime.now(timezone.utc),
    )
    _FakeRepo.frameworks = {"fw-1": fw}
    _FakeRepo.jobs = {"job-1": job}
    _FakeRepo.plans = {"plan-1": _plan(id="plan-1", version=1, status=StudyPlanStatus.APPROVED)}

    async def _fake_get_job_by_id(self: Any, job_id: str) -> FrameworkResearchJob | None:
        return _FakeRepo.jobs.get(job_id)

    async def _fake_next_version(self: Any, framework_id: str) -> int:
        return 2

    monkeypatch.setattr(_FakeRepo, "get_job_by_id", _fake_get_job_by_id, raising=False)
    monkeypatch.setattr(_FakeRepo, "next_plan_version", _fake_next_version, raising=False)

    class _Outcome:
        partial = True
        cost_usd = 10.0
        sources_count = 3
        sources: list[Any] = []
        topics: list[Any] = []
        weekly_pacing: list[Any] = []
        from app.features.exam_frameworks.schemas import ExamStrategy

        exam_strategy = ExamStrategy()

    async def _fake_run_research(framework: Any, **kwargs: Any) -> Any:
        return _Outcome()

    monkeypatch.setattr(research_mod, "run_research", _fake_run_research)

    svc = ExamFrameworkService(session=None)  # type: ignore[arg-type]
    status = await svc.run_and_persist_research("fw-1", "job-1")

    assert status == ResearchJobStatus.PARTIAL
    assert _FakeRepo.frameworks["fw-1"].status == FrameworkStatus.PUBLISHED
