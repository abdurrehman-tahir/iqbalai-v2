"""T-137 — version-by-version score timeline API (independent tenant, brief mirror)."""

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
from app.features.independent_users.models import IndependentUser, IndependentUserRole
from app.features.lectures.models import (
    IndependentLecture,
    IndependentLectureVersion,
    LectureStatus,
)

TEACHER = IndependentUser(
    id="ind-teacher-1",
    authentik_id="auth-ind-teacher",
    email="ind-teacher@example.com",
    display_name="Independent Teacher",
    role=IndependentUserRole.INDEPENDENT_TEACHER,
)

LECTURE = IndependentLecture(
    id="ind-lecture-1",
    teacher_user_id="ind-teacher-1",
    title="Newton's Laws",
    topic="Forces",
    status=LectureStatus.READY_FOR_EDIT,
    current_version_id="ind-version-3",
)

VERSIONS = [
    IndependentLectureVersion(
        id=f"ind-version-{n}",
        lecture_id="ind-lecture-1",
        version=n,
        body=f"Body v{n}.",
        scores_jsonb={"total": 30 + n},
        created_at=datetime.now(timezone.utc),
    )
    for n in range(1, 4)
]


class _FakeUserRepo:
    store: dict[str, IndependentUser] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def get_by_authentik_id(self, authentik_id: str) -> IndependentUser | None:
        return next((u for u in self.store.values() if u.authentik_id == authentik_id), None)


class _FakeLectureRepo:
    store: dict[str, IndependentLecture] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def get_by_id(self, lecture_id: str) -> IndependentLecture | None:
        return self.store.get(lecture_id)


class _FakeVersionRepo:
    store: dict[str, IndependentLectureVersion] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def list_paginated(
        self, lecture_id: str, *, page: int, page_size: int
    ) -> tuple[list[IndependentLectureVersion], int]:
        rows = sorted(
            (v for v in self.store.values() if v.lecture_id == lecture_id),
            key=lambda v: v.version,
            reverse=True,
        )
        start = (page - 1) * page_size
        return rows[start : start + page_size], len(rows)


@pytest.fixture(autouse=True)
def _patch_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    _FakeUserRepo.store = {TEACHER.id: TEACHER}
    _FakeLectureRepo.store = {LECTURE.id: LECTURE}
    _FakeVersionRepo.store = {v.id: v for v in VERSIONS}

    monkeypatch.setattr(
        "app.features.lectures.independent_service.IndependentUserRepository", _FakeUserRepo
    )
    monkeypatch.setattr(
        "app.features.lectures.independent_service.IndependentLectureRepository", _FakeLectureRepo
    )
    monkeypatch.setattr(
        "app.features.lectures.independent_service.IndependentLectureVersionRepository",
        _FakeVersionRepo,
    )


async def _fake_db() -> AsyncGenerator[None, None]:
    yield None


async def _fake_user() -> dict[str, object]:
    return {"sub": "auth-ind-teacher", "role": "independent_teacher", "user_id": "ind-teacher-1"}


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    app = FastAPI()
    setup_exception_handlers(app)
    app.include_router(v1_router, prefix="/api/v1")
    app.dependency_overrides[get_db] = _fake_db
    app.dependency_overrides[get_current_user] = _fake_user
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_lists_versions_newest_first(client: AsyncClient) -> None:
    res = await client.get("/api/v1/independent/teachers/me/lectures/ind-lecture-1/versions")
    assert res.status_code == 200
    body = res.json()
    assert body["total"] == 3
    assert [item["version"] for item in body["items"]] == [3, 2, 1]
    assert body["items"][0]["scores_jsonb"]["total"] == 33
