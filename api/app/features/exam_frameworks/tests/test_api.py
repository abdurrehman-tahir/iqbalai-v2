"""API contract tests for exam-framework CRUD — T-092.

Covers the five Platform-Admin routes: create (201, DRAFT), list (status filter),
get, update (DRAFT-gated), delete (soft, DRAFT-gated). Failure modes: non-Platform-
Admin -> 403, non-DRAFT edit/delete -> 409, out-of-range grade -> 422, missing -> 404.

Backend is faked with an in-memory ``_FakeFrameworkRepo`` monkeypatched onto the
service module, mirroring the house harness (dependency_overrides + ASGITransport).
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
from app.features.exam_frameworks.models import ExamFramework, FrameworkStatus


class _FakeFrameworkRepo:
    store: dict[str, ExamFramework] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def list_frameworks(
        self,
        status: FrameworkStatus | None = None,
        include_deleted: bool = False,
    ) -> list[ExamFramework]:
        rows = list(self.store.values())
        if not include_deleted:
            rows = [r for r in rows if r.deleted_at is None]
        if status is not None:
            rows = [r for r in rows if r.status == status]
        return sorted(rows, key=lambda r: r.created_at, reverse=True)

    async def get_by_id(self, id: str) -> ExamFramework | None:
        return self.store.get(id)

    async def create(self, framework: ExamFramework) -> ExamFramework:
        now = datetime.now(timezone.utc)
        framework.created_at = now
        framework.updated_at = now
        self.store[framework.id] = framework
        return framework

    async def update(self, framework: ExamFramework) -> ExamFramework:
        framework.updated_at = datetime.now(timezone.utc)
        self.store[framework.id] = framework
        return framework

    async def soft_delete(self, framework: ExamFramework) -> None:
        framework.deleted_at = datetime.now(timezone.utc)
        self.store[framework.id] = framework


def _seed(**overrides: Any) -> ExamFramework:
    now = datetime.now(timezone.utc)
    fields: dict[str, Any] = {
        "id": "fw-1",
        "name": "Matric Punjab — Physics",
        "exam_target": "Matric Punjab Board — Physics",
        "region": "Punjab",
        "target_grade_range": [9, 10],
        "language": "en",
        "status": FrameworkStatus.DRAFT,
        "created_by": "admin-1",
    }
    fields.update(overrides)
    fw = ExamFramework(**fields)
    fw.created_at = now
    fw.updated_at = now
    return fw


@pytest.fixture(autouse=True)
def _patch_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    _FakeFrameworkRepo.store = {}
    monkeypatch.setattr(
        "app.features.exam_frameworks.service.ExamFrameworkRepository",
        _FakeFrameworkRepo,
    )

    # CRUD + research-trigger now audit (T-098); stub it (tests run without a live session).
    async def _noop_audit(**kwargs: object) -> None:
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
async def test_create_framework_returns_draft() -> None:
    async with _build_client() as client:
        resp = await client.post(
            "/api/v1/exam-frameworks/",
            json={
                "name": "Matric Punjab — Physics",
                "exam_target": "Matric Punjab Board — Physics",
                "region": "Punjab",
                "target_grade_range": [9, 10],
            },
        )

    assert resp.status_code == 201
    body = resp.json()["data"]
    assert body["status"] == "draft"
    assert body["created_by"] == "admin-1"
    assert body["target_grade_range"] == [9, 10]


@pytest.mark.asyncio
async def test_create_forbidden_for_non_platform_admin() -> None:
    async with _build_client(role="school_admin") as client:
        resp = await client.post(
            "/api/v1/exam-frameworks/",
            json={
                "name": "X",
                "exam_target": "Y",
                "region": "Punjab",
                "target_grade_range": [9],
            },
        )

    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_create_rejects_out_of_range_grade() -> None:
    async with _build_client() as client:
        resp = await client.post(
            "/api/v1/exam-frameworks/",
            json={
                "name": "X",
                "exam_target": "Y",
                "region": "Punjab",
                "target_grade_range": [0, 99],
            },
        )

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_list_filters_by_status() -> None:
    _FakeFrameworkRepo.store = {
        "fw-1": _seed(id="fw-1", status=FrameworkStatus.DRAFT),
        "fw-2": _seed(id="fw-2", status=FrameworkStatus.PUBLISHED),
    }
    async with _build_client() as client:
        resp = await client.get("/api/v1/exam-frameworks/?status=published")

    assert resp.status_code == 200
    rows = resp.json()["data"]
    assert [r["id"] for r in rows] == ["fw-2"]


@pytest.mark.asyncio
async def test_get_missing_returns_404() -> None:
    async with _build_client() as client:
        resp = await client.get("/api/v1/exam-frameworks/nope")

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_draft_succeeds() -> None:
    _FakeFrameworkRepo.store = {"fw-1": _seed()}
    async with _build_client() as client:
        resp = await client.put(
            "/api/v1/exam-frameworks/fw-1",
            json={"region": "Sindh"},
        )

    assert resp.status_code == 200
    assert resp.json()["data"]["region"] == "Sindh"


@pytest.mark.asyncio
async def test_update_non_draft_conflicts() -> None:
    _FakeFrameworkRepo.store = {"fw-1": _seed(status=FrameworkStatus.PUBLISHED)}
    async with _build_client() as client:
        resp = await client.put(
            "/api/v1/exam-frameworks/fw-1",
            json={"region": "Sindh"},
        )

    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_delete_draft_soft_deletes() -> None:
    _FakeFrameworkRepo.store = {"fw-1": _seed()}
    async with _build_client() as client:
        resp = await client.delete("/api/v1/exam-frameworks/fw-1")

    assert resp.status_code == 200
    assert _FakeFrameworkRepo.store["fw-1"].deleted_at is not None


@pytest.mark.asyncio
async def test_delete_non_draft_conflicts() -> None:
    _FakeFrameworkRepo.store = {"fw-1": _seed(status=FrameworkStatus.PUBLISHED)}
    async with _build_client() as client:
        resp = await client.delete("/api/v1/exam-frameworks/fw-1")

    assert resp.status_code == 409
