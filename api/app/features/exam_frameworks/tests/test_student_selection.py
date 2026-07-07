"""Student framework selection + rendering + region scoping tests — T-096
(Flow 4 §3.5.2/§3.5.3, ARCH §3.19).

Covers browse with region + grade scoping (Punjab student sees Punjab + "any", not
Sindh; grade band filtered), select -> ACTIVE pinned to current version, duplicate-select
guard, multiple different frameworks, the opt-in switch banner (update_available) + switch,
study-plan rendering (self-study hook), drop -> ABANDONED (history retained), ownership
isolation, and the non-student 403. Backend is an in-memory fake repo; user resolution
(app user id per tenant) is stubbed.
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
    FrameworkStatus,
    FrameworkStudyPlan,
    SelectionStatus,
    SelectionTenantType,
    StudentFrameworkSelection,
    StudyPlanStatus,
)
from app.features.exam_frameworks.student_repository import REGION_ANY


class _FakeRepo:
    frameworks: dict[str, ExamFramework] = {}
    plans: dict[str, FrameworkStudyPlan] = {}
    selections: dict[str, StudentFrameworkSelection] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def list_available_frameworks(self, region: str, grade: int) -> list[ExamFramework]:
        return [
            f
            for f in self.frameworks.values()
            if f.status == FrameworkStatus.PUBLISHED
            and f.deleted_at is None
            and (f.region == region or f.region == REGION_ANY)
            and grade in f.target_grade_range
        ]

    async def get_published_framework(self, framework_id: str) -> ExamFramework | None:
        f = self.frameworks.get(framework_id)
        if f is None or f.status != FrameworkStatus.PUBLISHED or f.deleted_at is not None:
            return None
        return f

    async def get_framework(self, framework_id: str) -> ExamFramework | None:
        f = self.frameworks.get(framework_id)
        return f if f is not None and f.deleted_at is None else None

    async def get_current_published_plan(self, framework_id: str) -> FrameworkStudyPlan | None:
        appr = [
            p
            for p in self.plans.values()
            if p.framework_id == framework_id and p.status == StudyPlanStatus.APPROVED
        ]
        return max(appr, key=lambda p: p.version) if appr else None

    async def get_plan_by_version(
        self, framework_id: str, version: int
    ) -> FrameworkStudyPlan | None:
        for p in self.plans.values():
            if p.framework_id == framework_id and p.version == version:
                return p
        return None

    async def list_selections(
        self, tenant_type: SelectionTenantType, student_user_id: str
    ) -> list[StudentFrameworkSelection]:
        return [
            s
            for s in self.selections.values()
            if s.tenant_type == tenant_type
            and s.student_user_id == student_user_id
            and s.deleted_at is None
        ]

    async def get_active_selection(
        self, tenant_type: SelectionTenantType, student_user_id: str, framework_id: str
    ) -> StudentFrameworkSelection | None:
        for s in self.selections.values():
            if (
                s.tenant_type == tenant_type
                and s.student_user_id == student_user_id
                and s.framework_id == framework_id
                and s.status == SelectionStatus.ACTIVE
                and s.deleted_at is None
            ):
                return s
        return None

    async def get_selection_by_id(self, selection_id: str) -> StudentFrameworkSelection | None:
        s = self.selections.get(selection_id)
        return s if s is not None and s.deleted_at is None else None

    def add(self, selection: StudentFrameworkSelection) -> None:
        now = datetime.now(timezone.utc)
        selection.created_at = now
        selection.updated_at = now
        self.selections[selection.id] = selection

    async def commit(self) -> None:
        pass

    async def refresh(self, selection: StudentFrameworkSelection) -> None:
        pass


class _FakeUser:
    def __init__(self, id: str) -> None:
        self.id = id


class _FakeUserRepo:
    def __init__(self, session: Any) -> None:
        pass

    async def get_by_authentik_id(self, authentik_id: str) -> _FakeUser:
        return _FakeUser(id="stu-1")


def _framework(**overrides: Any) -> ExamFramework:
    now = datetime.now(timezone.utc)
    fields: dict[str, Any] = {
        "id": "fw-1",
        "name": "Matric Punjab — Physics",
        "exam_target": "Matric Punjab Board — Physics",
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
        "content_jsonb": {
            "topics": [{"topic_name": "Kinematics"}],
            "weekly_pacing": [{}],
            "exam_strategy": {},
        },
        "sources_cited_jsonb": [{"url": "https://ex.com", "title": "Past papers"}],
        "generated_at": now,
        "status": StudyPlanStatus.APPROVED,
    }
    fields.update(overrides)
    plan = FrameworkStudyPlan(**fields)
    plan.created_at = now
    plan.updated_at = now
    return plan


def _selection(**overrides: Any) -> StudentFrameworkSelection:
    now = datetime.now(timezone.utc)
    fields: dict[str, Any] = {
        "id": "sel-1",
        "tenant_type": SelectionTenantType.SCHOOL,
        "student_user_id": "stu-1",
        "framework_id": "fw-1",
        "pinned_version": 1,
        "status": SelectionStatus.ACTIVE,
        "selected_at": now,
    }
    fields.update(overrides)
    sel = StudentFrameworkSelection(**fields)
    sel.created_at = now
    sel.updated_at = now
    return sel


@pytest.fixture(autouse=True)
def _patch_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    _FakeRepo.frameworks = {}
    _FakeRepo.plans = {}
    _FakeRepo.selections = {}
    monkeypatch.setattr(
        "app.features.exam_frameworks.student_service.StudentFrameworkRepository", _FakeRepo
    )
    monkeypatch.setattr(
        "app.features.exam_frameworks.student_service.UserRepository", _FakeUserRepo
    )
    monkeypatch.setattr(
        "app.features.exam_frameworks.student_service.IndependentUserRepository", _FakeUserRepo
    )


def _build_client(role: str = "student", tenant_type: str = "school") -> AsyncClient:
    app = FastAPI()
    app.include_router(v1_router, prefix="/api/v1")
    setup_exception_handlers(app)

    async def _override_db() -> AsyncGenerator[None, None]:
        yield None

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = lambda: {
        "sub": "auth-1",
        "role": role,
        "tenant_type": tenant_type,
    }
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_available_region_and_grade_scoping() -> None:
    _FakeRepo.frameworks = {
        "fw-1": _framework(id="fw-1", region="Punjab", target_grade_range=[9, 10]),
        "fw-any": _framework(id="fw-any", name="NTS", region=REGION_ANY, target_grade_range=[10]),
        "fw-sindh": _framework(
            id="fw-sindh", name="Sindh", region="Sindh", target_grade_range=[10]
        ),
        "fw-grade": _framework(
            id="fw-grade", name="FSc", region="Punjab", target_grade_range=[11, 12]
        ),
    }
    _FakeRepo.plans = {
        "p1": _plan(id="p1", framework_id="fw-1"),
        "p2": _plan(id="p2", framework_id="fw-any"),
        "p3": _plan(id="p3", framework_id="fw-sindh"),
        "p4": _plan(id="p4", framework_id="fw-grade"),
    }
    async with _build_client() as client:
        resp = await client.get("/api/v1/student/exam-frameworks/available?region=Punjab&grade=10")

    assert resp.status_code == 200
    ids = {f["id"] for f in resp.json()["data"]}
    assert ids == {"fw-1", "fw-any"}  # Punjab + any; not Sindh; grade 10 excludes FSc(11-12)


@pytest.mark.asyncio
async def test_select_creates_active_pinned_selection() -> None:
    _FakeRepo.frameworks = {"fw-1": _framework()}
    _FakeRepo.plans = {"p1": _plan(version=3)}
    async with _build_client() as client:
        resp = await client.post("/api/v1/student/exam-frameworks/fw-1/select")

    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["status"] == "active"
    assert data["pinned_version"] == 3
    assert data["framework_name"] == "Matric Punjab — Physics"


@pytest.mark.asyncio
async def test_select_duplicate_active_conflicts() -> None:
    _FakeRepo.frameworks = {"fw-1": _framework()}
    _FakeRepo.plans = {"p1": _plan()}
    _FakeRepo.selections = {"sel-1": _selection()}
    async with _build_client() as client:
        resp = await client.post("/api/v1/student/exam-frameworks/fw-1/select")

    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_select_unavailable_framework_404() -> None:
    _FakeRepo.frameworks = {"fw-1": _framework(status=FrameworkStatus.DEPRECATED)}
    async with _build_client() as client:
        resp = await client.post("/api/v1/student/exam-frameworks/fw-1/select")

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_multiple_different_frameworks_allowed() -> None:
    _FakeRepo.frameworks = {
        "fw-1": _framework(id="fw-1"),
        "fw-2": _framework(id="fw-2", name="NTS"),
    }
    _FakeRepo.plans = {
        "p1": _plan(id="p1", framework_id="fw-1"),
        "p2": _plan(id="p2", framework_id="fw-2"),
    }
    _FakeRepo.selections = {"sel-1": _selection(id="sel-1", framework_id="fw-1")}
    async with _build_client() as client:
        resp = await client.post("/api/v1/student/exam-frameworks/fw-2/select")

    assert resp.status_code == 201
    assert len(_FakeRepo.selections) == 2


@pytest.mark.asyncio
async def test_selections_flag_update_available() -> None:
    _FakeRepo.frameworks = {"fw-1": _framework()}
    _FakeRepo.plans = {"p2": _plan(id="p2", version=2)}  # latest published = v2
    _FakeRepo.selections = {"sel-1": _selection(pinned_version=1)}  # pinned to v1
    async with _build_client() as client:
        resp = await client.get("/api/v1/student/exam-frameworks/selections")

    assert resp.status_code == 200
    sel = resp.json()["data"][0]
    assert sel["latest_version"] == 2
    assert sel["update_available"] is True


@pytest.mark.asyncio
async def test_study_plan_renders_pinned_version() -> None:
    _FakeRepo.frameworks = {"fw-1": _framework()}
    _FakeRepo.plans = {
        "p1": _plan(id="p1", version=1),
        "p2": _plan(id="p2", version=2, content_jsonb={"topics": [], "weekly_pacing": []}),
    }
    _FakeRepo.selections = {"sel-1": _selection(pinned_version=1)}
    async with _build_client() as client:
        resp = await client.get("/api/v1/student/exam-frameworks/selections/sel-1/study-plan")

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["version"] == 1
    assert data["content_jsonb"]["topics"][0]["topic_name"] == "Kinematics"


@pytest.mark.asyncio
async def test_switch_bumps_pinned_to_latest() -> None:
    _FakeRepo.frameworks = {"fw-1": _framework()}
    _FakeRepo.plans = {"p2": _plan(id="p2", version=2)}
    _FakeRepo.selections = {"sel-1": _selection(pinned_version=1)}
    async with _build_client() as client:
        resp = await client.post("/api/v1/student/exam-frameworks/selections/sel-1/switch")

    assert resp.status_code == 200
    assert resp.json()["data"]["pinned_version"] == 2
    assert _FakeRepo.selections["sel-1"].pinned_version == 2


@pytest.mark.asyncio
async def test_drop_marks_abandoned_and_retains_row() -> None:
    _FakeRepo.frameworks = {"fw-1": _framework()}
    _FakeRepo.plans = {"p1": _plan()}
    _FakeRepo.selections = {"sel-1": _selection()}
    async with _build_client() as client:
        resp = await client.delete("/api/v1/student/exam-frameworks/selections/sel-1")

    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "abandoned"
    assert _FakeRepo.selections["sel-1"].status == SelectionStatus.ABANDONED


@pytest.mark.asyncio
async def test_cannot_touch_another_students_selection() -> None:
    _FakeRepo.frameworks = {"fw-1": _framework()}
    _FakeRepo.plans = {"p1": _plan()}
    _FakeRepo.selections = {"sel-1": _selection(student_user_id="someone-else")}
    async with _build_client() as client:
        resp = await client.post("/api/v1/student/exam-frameworks/selections/sel-1/switch")

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_non_student_forbidden() -> None:
    _FakeRepo.frameworks = {"fw-1": _framework()}
    _FakeRepo.plans = {"p1": _plan()}
    async with _build_client(role="teacher") as client:
        resp = await client.get("/api/v1/student/exam-frameworks/available?region=Punjab&grade=10")

    assert resp.status_code == 403
