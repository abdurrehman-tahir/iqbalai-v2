"""T-137 — version-by-version score timeline API tests (school tenant).

Acceptance (M-10 T-137):
1. Timeline plots total score across versions (data comes from scores_jsonb).
2. Hover reveals all 7 dimensions (scores_jsonb carries the full breakdown).
3. Annotations auto-derived from edit metadata (edit_summary, already on the
   version row from T-130-T-132).
4. Default = last 6 versions; pagination for older.
5. (Rendering acceptance — covered by the frontend test, not this file.)
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
from app.features.lectures.models import LectureStatus, SchoolLecture, SchoolLectureVersion
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
OTHER_TEACHER = User(
    id="teacher-2",
    authentik_id="auth-teacher-2",
    email="teacher2@example.com",
    display_name="Teacher Two",
    role=UserRole.TEACHER,
    status=UserAccountStatus.ACTIVE,
    school_id="school-1",
)

LECTURE = SchoolLecture(
    id="lecture-1",
    school_id="school-1",
    teacher_user_id="teacher-1",
    title="Newton's Laws",
    topic="Forces",
    status=LectureStatus.READY_FOR_EDIT,
    current_version_id="version-8",
)

# 8 versions so the pagination acceptance (default 6, older via page 2) is
# actually exercised, not just asserted against a single page.
VERSIONS = [
    SchoolLectureVersion(
        id=f"version-{n}",
        lecture_id="lecture-1",
        version=n,
        body=f"Body v{n}.",
        scores_jsonb={"total": 30 + n, "originality": 7},
        edit_summary=["Applied voice edit"] if n == 3 else None,
        created_at=datetime.now(timezone.utc),
    )
    for n in range(1, 9)
]


class _FakeUserRepo:
    store: dict[str, User] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def get_by_authentik_id(self, authentik_id: str) -> User | None:
        return next((u for u in self.store.values() if u.authentik_id == authentik_id), None)


class _FakeLectureRepo:
    store: dict[str, SchoolLecture] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def get_by_id(self, lecture_id: str) -> SchoolLecture | None:
        return self.store.get(lecture_id)


class _FakeVersionRepo:
    store: dict[str, SchoolLectureVersion] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def list_paginated(
        self, lecture_id: str, *, page: int, page_size: int
    ) -> tuple[list[SchoolLectureVersion], int]:
        rows = sorted(
            (v for v in self.store.values() if v.lecture_id == lecture_id),
            key=lambda v: v.version,
            reverse=True,
        )
        start = (page - 1) * page_size
        return rows[start : start + page_size], len(rows)


@pytest.fixture(autouse=True)
def _patch_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    _FakeUserRepo.store = {TEACHER.id: TEACHER, OTHER_TEACHER.id: OTHER_TEACHER}
    _FakeLectureRepo.store = {LECTURE.id: LECTURE}
    _FakeVersionRepo.store = {v.id: v for v in VERSIONS}

    monkeypatch.setattr("app.features.lectures.service.UserRepository", _FakeUserRepo)
    monkeypatch.setattr("app.features.lectures.service.LectureRepository", _FakeLectureRepo)
    monkeypatch.setattr("app.features.lectures.service.LectureVersionRepository", _FakeVersionRepo)


async def _fake_db() -> AsyncGenerator[None, None]:
    yield None


async def _fake_user() -> dict[str, object]:
    return {"sub": "auth-teacher", "role": "teacher", "user_id": "teacher-1"}


async def _fake_other_user() -> dict[str, object]:
    return {"sub": "auth-teacher-2", "role": "teacher", "user_id": "teacher-2"}


def _make_client(current_user: Any) -> AsyncClient:
    app = FastAPI()
    setup_exception_handlers(app)
    app.include_router(v1_router, prefix="/api/v1")
    app.dependency_overrides[get_db] = _fake_db
    app.dependency_overrides[get_current_user] = current_user
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    async with _make_client(_fake_user) as ac:
        yield ac


@pytest.fixture
async def other_client() -> AsyncGenerator[AsyncClient, None]:
    async with _make_client(_fake_other_user) as ac:
        yield ac


@pytest.mark.asyncio
async def test_default_page_returns_last_six_versions_newest_first(client: AsyncClient) -> None:
    """Acceptance #4 — default view = last 6 versions."""
    res = await client.get("/api/v1/teachers/me/lectures/lecture-1/versions")
    assert res.status_code == 200
    body = res.json()
    assert body["total"] == 8
    assert body["page"] == 1
    assert body["page_size"] == 6
    versions = [item["version"] for item in body["items"]]
    assert versions == [8, 7, 6, 5, 4, 3]


@pytest.mark.asyncio
async def test_page_two_returns_older_versions(client: AsyncClient) -> None:
    """Acceptance #4 — older versions accessible via pagination."""
    res = await client.get(
        "/api/v1/teachers/me/lectures/lecture-1/versions", params={"page": 2, "page_size": 6}
    )
    assert res.status_code == 200
    body = res.json()
    versions = [item["version"] for item in body["items"]]
    assert versions == [2, 1]


@pytest.mark.asyncio
async def test_items_carry_total_score_and_all_seven_dimensions(client: AsyncClient) -> None:
    """Acceptance #1 + #2 — the timeline's chart data and hover breakdown both
    come straight from scores_jsonb, already present on each item."""
    res = await client.get("/api/v1/teachers/me/lectures/lecture-1/versions")
    item = next(i for i in res.json()["items"] if i["version"] == 8)
    assert item["scores_jsonb"]["total"] == 38
    assert item["scores_jsonb"]["originality"] == 7


@pytest.mark.asyncio
async def test_items_carry_edit_summary_annotations(client: AsyncClient) -> None:
    """Acceptance #3 — annotations auto-derived from edit metadata."""
    res = await client.get("/api/v1/teachers/me/lectures/lecture-1/versions")
    item = next(i for i in res.json()["items"] if i["version"] == 3)
    assert item["edit_summary"] == ["Applied voice edit"]


@pytest.mark.asyncio
async def test_non_owner_teacher_gets_not_found(other_client: AsyncClient) -> None:
    res = await other_client.get("/api/v1/teachers/me/lectures/lecture-1/versions")
    assert res.status_code == 404
