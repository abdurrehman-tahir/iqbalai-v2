"""T-139 — admin comparative teacher metrics API (Flow 5 §3.11 #38)."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.v1.router import router as v1_router
from app.core.dependencies import get_current_user, get_db
from app.core.exceptions import setup_exception_handlers
from app.core.tests.test_idempotency import FakeRedis
from app.features.admin_metrics.repository import TeacherMetricsRow

ROW = TeacherMetricsRow(
    teacher_user_id="t-1",
    teacher_name="Teacher One",
    school_id="school-1",
    school_name="School One",
    subject_id="subj-1",
    subject_name="Mathematics",
    grade_level_ordinal="9",
    lecture_id="lec-1",
    scores_jsonb={
        "originality": 8,
        "depth": 7,
        "cultural_relevance": 4,
        "engagement": 4,
        "alignment": 9,
        "voice_quality": None,
        "ai_learning": 6,
        "total": 38,
    },
    topic_relevance_pct=80.0,
)


class _FakeRepo:
    rows: list[TeacherMetricsRow] = []

    def __init__(self, session: Any) -> None:
        pass

    async def list_scored_versions(
        self, *, school_ids: list[str] | None
    ) -> list[TeacherMetricsRow]:
        if school_ids is None:
            return list(self.rows)
        return [r for r in self.rows if r.school_id in school_ids]

    async def list_school_ids_for_district(self, district_id: str) -> list[str]:
        return []


@pytest.fixture(autouse=True)
def _patch_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    _FakeRepo.rows = [ROW]
    monkeypatch.setattr(
        "app.features.admin_metrics.service.AdminTeacherMetricsRepository", _FakeRepo
    )
    monkeypatch.setattr("app.features.admin_metrics.service.get_redis", lambda: FakeRedis())


async def _fake_db() -> AsyncGenerator[None, None]:
    yield None


async def _school_admin_claims() -> dict[str, object]:
    return {"sub": "auth-admin", "role": "school_admin", "school_id": "school-1"}


async def _teacher_claims() -> dict[str, object]:
    return {"sub": "auth-teacher", "role": "teacher", "school_id": "school-1"}


def _make_client(current_user: Any) -> AsyncClient:
    app = FastAPI()
    setup_exception_handlers(app)
    app.include_router(v1_router, prefix="/api/v1")
    app.dependency_overrides[get_db] = _fake_db
    app.dependency_overrides[get_current_user] = current_user
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.fixture
async def admin_client() -> AsyncGenerator[AsyncClient, None]:
    async with _make_client(_school_admin_claims) as ac:
        yield ac


@pytest.fixture
async def teacher_client() -> AsyncGenerator[AsyncClient, None]:
    async with _make_client(_teacher_claims) as ac:
        yield ac


@pytest.mark.asyncio
async def test_list_teacher_metrics_returns_aggregated_row(admin_client: AsyncClient) -> None:
    res = await admin_client.get("/api/v1/admin/teacher-metrics")
    assert res.status_code == 200
    items = res.json()["data"]
    assert len(items) == 1
    assert items[0]["teacher_name"] == "Teacher One"
    assert items[0]["avg_total"] == 38.0
    assert items[0]["lecture_count"] == 1


@pytest.mark.asyncio
async def test_teacher_role_is_forbidden(teacher_client: AsyncClient) -> None:
    res = await teacher_client.get("/api/v1/admin/teacher-metrics")
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_csv_export_returns_csv_content_type(admin_client: AsyncClient) -> None:
    res = await admin_client.get("/api/v1/admin/teacher-metrics/export")
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/csv")
    assert "Teacher One" in res.text
    assert "teacher_name" in res.text.splitlines()[0]


@pytest.mark.asyncio
async def test_subject_filter_query_param(admin_client: AsyncClient) -> None:
    res = await admin_client.get("/api/v1/admin/teacher-metrics", params={"subject_id": "subj-2"})
    assert res.status_code == 200
    assert res.json()["data"] == []
