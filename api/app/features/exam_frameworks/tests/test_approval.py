"""Approval-workflow tests — T-094 (Flow 4 §3.5.1, ARCH §3.19).

Covers the Platform-Admin review surface (GET plan), approve (-> PUBLISHED),
reject (-> DRAFT + reviewer notes), the status guards (409 when not pending), the
403 non-Platform-Admin denial, and the approval-SLA sweep (reminder@7d /
escalation@14d, idempotent). Backend is the in-memory fake repo used across the
feature's API tests; ``audit`` is stubbed since these run without a live session.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.v1.router import router as v1_router
from app.core.dependencies import get_current_user, get_db
from app.core.exceptions import setup_exception_handlers
from app.features.exam_frameworks.models import (
    ExamFramework,
    FrameworkStatus,
    FrameworkStudyPlan,
    StudyPlanStatus,
)
from app.features.exam_frameworks.service import ExamFrameworkService


class _FakeRepo:
    frameworks: dict[str, ExamFramework] = {}
    plans: dict[str, FrameworkStudyPlan] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def get_by_id(self, id: str) -> ExamFramework | None:
        return self.frameworks.get(id)

    async def get_pending_plan(self, framework_id: str) -> FrameworkStudyPlan | None:
        pend = [
            p
            for p in self.plans.values()
            if p.framework_id == framework_id and p.status == StudyPlanStatus.PENDING_APPROVAL
        ]
        return max(pend, key=lambda p: p.version) if pend else None

    async def get_current_published_plan(self, framework_id: str) -> FrameworkStudyPlan | None:
        appr = [
            p
            for p in self.plans.values()
            if p.framework_id == framework_id and p.status == StudyPlanStatus.APPROVED
        ]
        return max(appr, key=lambda p: p.version) if appr else None

    async def list_pending_approval_frameworks(self) -> list[ExamFramework]:
        return [
            f
            for f in self.frameworks.values()
            if f.status == FrameworkStatus.PENDING_APPROVAL and f.deleted_at is None
        ]

    def add(self, obj: Any) -> None:
        pass

    async def commit(self) -> None:
        pass

    async def refresh(self, obj: Any) -> None:
        pass


def _framework(**overrides: Any) -> ExamFramework:
    now = datetime.now(timezone.utc)
    fields: dict[str, Any] = {
        "id": "fw-1",
        "name": "Matric Punjab — Physics",
        "exam_target": "Matric Punjab Board — Physics",
        "region": "Punjab",
        "target_grade_range": [9, 10],
        "language": "en",
        "status": FrameworkStatus.PENDING_APPROVAL,
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
        "status": StudyPlanStatus.PENDING_APPROVAL,
    }
    fields.update(overrides)
    plan = FrameworkStudyPlan(**fields)
    plan.created_at = now
    plan.updated_at = now
    return plan


@pytest.fixture(autouse=True)
def _patch_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    _FakeRepo.frameworks = {}
    _FakeRepo.plans = {}
    monkeypatch.setattr("app.features.exam_frameworks.service.ExamFrameworkRepository", _FakeRepo)

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
async def test_review_returns_plan_content_and_sources() -> None:
    _FakeRepo.frameworks = {"fw-1": _framework()}
    _FakeRepo.plans = {"plan-1": _plan()}
    async with _build_client() as client:
        resp = await client.get("/api/v1/exam-frameworks/fw-1/plan")

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["version"] == 1
    assert data["sources_cited_jsonb"][0]["url"] == "https://ex.com"


@pytest.mark.asyncio
async def test_review_404_when_not_pending() -> None:
    _FakeRepo.frameworks = {"fw-1": _framework(status=FrameworkStatus.DRAFT)}
    async with _build_client() as client:
        resp = await client.get("/api/v1/exam-frameworks/fw-1/plan")

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_approve_publishes_and_supersedes_prior() -> None:
    _FakeRepo.frameworks = {"fw-1": _framework()}
    _FakeRepo.plans = {
        "plan-0": _plan(id="plan-0", version=0, status=StudyPlanStatus.APPROVED),
        "plan-1": _plan(),
    }
    async with _build_client() as client:
        resp = await client.post("/api/v1/exam-frameworks/fw-1/approve")

    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "approved"
    assert _FakeRepo.frameworks["fw-1"].status == FrameworkStatus.PUBLISHED
    assert _FakeRepo.plans["plan-0"].status == StudyPlanStatus.SUPERSEDED
    assert _FakeRepo.plans["plan-1"].approved_by == "admin-1"


@pytest.mark.asyncio
async def test_approve_conflicts_when_not_pending() -> None:
    _FakeRepo.frameworks = {"fw-1": _framework(status=FrameworkStatus.PUBLISHED)}
    async with _build_client() as client:
        resp = await client.post("/api/v1/exam-frameworks/fw-1/approve")

    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_reject_reverts_to_draft_with_notes() -> None:
    _FakeRepo.frameworks = {"fw-1": _framework()}
    _FakeRepo.plans = {"plan-1": _plan()}
    async with _build_client() as client:
        resp = await client.post(
            "/api/v1/exam-frameworks/fw-1/reject",
            json={"notes": "Topic weights look off; re-run research."},
        )

    assert resp.status_code == 200
    assert _FakeRepo.frameworks["fw-1"].status == FrameworkStatus.DRAFT
    assert _FakeRepo.plans["plan-1"].status == StudyPlanStatus.DRAFT
    notes = _FakeRepo.plans["plan-1"].reviewer_notes
    assert notes is not None and notes.startswith("Topic weights")


@pytest.mark.asyncio
async def test_reject_requires_notes() -> None:
    _FakeRepo.frameworks = {"fw-1": _framework()}
    _FakeRepo.plans = {"plan-1": _plan()}
    async with _build_client() as client:
        resp = await client.post("/api/v1/exam-frameworks/fw-1/reject", json={"notes": ""})

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_approve_forbidden_for_non_platform_admin() -> None:
    _FakeRepo.frameworks = {"fw-1": _framework()}
    _FakeRepo.plans = {"plan-1": _plan()}
    async with _build_client(role="school_admin") as client:
        resp = await client.post("/api/v1/exam-frameworks/fw-1/approve")

    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_sla_sweep_fires_reminder_then_escalation_idempotently(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _FakeRepo.frameworks = {"fw-1": _framework()}

    async def _noop_audit(**kwargs: Any) -> None:
        return None

    monkeypatch.setattr("app.features.exam_frameworks.service.audit", _noop_audit)

    # 8 days old -> reminder marker fires once, then no-op on the second sweep.
    _FakeRepo.plans = {"plan-1": _plan(generated_at=datetime.now(timezone.utc) - timedelta(days=8))}
    svc = ExamFrameworkService(session=None)  # type: ignore[arg-type]
    assert await svc.sweep_approval_sla() == 1
    assert _FakeRepo.plans["plan-1"].sla_reminders_sent == "7"
    assert await svc.sweep_approval_sla() == 0

    # 15 days old -> escalation marker fires (reminder already recorded).
    _FakeRepo.plans["plan-1"].generated_at = datetime.now(timezone.utc) - timedelta(days=15)
    assert await svc.sweep_approval_sla() == 1
    assert _FakeRepo.plans["plan-1"].sla_reminders_sent == "7,14"
