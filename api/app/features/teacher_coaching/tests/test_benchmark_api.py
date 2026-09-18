"""T-139 — teacher benchmark API tests (school tenant, Flow 5 §3.11 #37)."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.v1.router import router as v1_router
from app.core.dependencies import get_current_user, get_db
from app.core.exceptions import setup_exception_handlers
from app.features.audit.actions import BENCHMARK_OPT_OUT_TOGGLED
from app.features.teacher_coaching.models import SchoolTeacherBenchmark
from app.features.users.models import User, UserAccountStatus, UserRole

TEACHER = User(
    id="teacher-1",
    authentik_id="auth-teacher",
    email="teacher@example.com",
    display_name="Teacher One",
    role=UserRole.TEACHER,
    status=UserAccountStatus.ACTIVE,
    school_id="school-1",
)

BENCHMARK_ROW = SchoolTeacherBenchmark(
    teacher_user_id="teacher-1",
    subject_id="subj-1",
    grade_range="9",
    region="Punjab",
    percentile=77,
    cohort_size=10,
)


class _FakeUserRepo:
    store: dict[str, User] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def get_by_authentik_id(self, authentik_id: str) -> User | None:
        return next((u for u in self.store.values() if u.authentik_id == authentik_id), None)


class _FakeBenchmarkRepo:
    rows: list[SchoolTeacherBenchmark] = []
    opt_out_calls: list[tuple[str, bool]] = []

    def __init__(self, session: Any) -> None:
        pass

    async def list_for_teacher_with_subject_name(
        self, teacher_user_id: str
    ) -> list[tuple[SchoolTeacherBenchmark, str]]:
        return [
            (row, "Mathematics")
            for row in self.rows
            if row.teacher_user_id == teacher_user_id
            and not row.opted_out
            and row.percentile is not None
        ]

    async def list_all_for_teacher(self, teacher_user_id: str) -> list[SchoolTeacherBenchmark]:
        return [row for row in self.rows if row.teacher_user_id == teacher_user_id]

    async def commit(self) -> None:
        pass


@pytest.fixture
def audit_mock(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    BENCHMARK_ROW.opted_out = False
    BENCHMARK_ROW.percentile = 77
    BENCHMARK_ROW.cohort_size = 10
    _FakeUserRepo.store = {TEACHER.id: TEACHER}
    _FakeBenchmarkRepo.rows = [BENCHMARK_ROW]
    _FakeBenchmarkRepo.opt_out_calls = []

    monkeypatch.setattr("app.features.teacher_coaching.service.UserRepository", _FakeUserRepo)
    monkeypatch.setattr(
        "app.features.teacher_coaching.benchmark_service.SchoolTeacherBenchmarkRepository",
        _FakeBenchmarkRepo,
    )
    mock = AsyncMock()
    monkeypatch.setattr("app.features.teacher_coaching.router.audit", mock)
    return mock


@pytest.fixture(autouse=True)
def _patch_backend(audit_mock: AsyncMock) -> None:
    pass


async def _fake_db() -> AsyncGenerator[None, None]:
    yield None


async def _fake_user() -> dict[str, object]:
    return {"sub": "auth-teacher", "role": "teacher", "user_id": "teacher-1"}


def _make_client() -> AsyncClient:
    app = FastAPI()
    setup_exception_handlers(app)
    app.include_router(v1_router, prefix="/api/v1")
    app.dependency_overrides[get_db] = _fake_db
    app.dependency_overrides[get_current_user] = _fake_user
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    async with _make_client() as ac:
        yield ac


@pytest.mark.asyncio
async def test_list_benchmarks_returns_top_percent(client: AsyncClient) -> None:
    res = await client.get("/api/v1/teachers/me/benchmarks")
    assert res.status_code == 200
    items = res.json()["data"]
    assert len(items) == 1
    assert items[0]["subject_name"] == "Mathematics"
    assert items[0]["top_percent"] == 23


@pytest.mark.asyncio
async def test_list_benchmarks_excludes_opted_out(client: AsyncClient) -> None:
    BENCHMARK_ROW.opted_out = True
    res = await client.get("/api/v1/teachers/me/benchmarks")
    assert res.status_code == 200
    assert res.json()["data"] == []


@pytest.mark.asyncio
async def test_opt_out_flips_existing_rows(client: AsyncClient) -> None:
    res = await client.post("/api/v1/teachers/me/benchmarks/opt-out", json={"opted_out": True})
    assert res.status_code == 200
    assert res.json()["data"] == {"rows_changed": 1}
    assert BENCHMARK_ROW.opted_out is True
    assert BENCHMARK_ROW.percentile is None
    assert BENCHMARK_ROW.cohort_size is None


@pytest.mark.asyncio
async def test_opt_out_rejects_missing_body_field(client: AsyncClient) -> None:
    res = await client.post("/api/v1/teachers/me/benchmarks/opt-out", json={})
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_opt_out_is_audit_logged(client: AsyncClient, audit_mock: AsyncMock) -> None:
    await client.post("/api/v1/teachers/me/benchmarks/opt-out", json={"opted_out": True})
    audit_mock.assert_awaited_once()
    assert audit_mock.call_args.kwargs["action"] == BENCHMARK_OPT_OUT_TOGGLED
    assert audit_mock.call_args.kwargs["metadata"]["opted_out"] is True
