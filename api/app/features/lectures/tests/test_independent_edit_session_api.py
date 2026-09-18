"""T-133 — effort-tracking edit session API tests (independent tenant, brief mirror)."""

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
    IndependentLectureEditSession,
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
    current_version_id="ind-version-1",
)


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


class _FakeEditSessionRepo:
    store: dict[str, IndependentLectureEditSession] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def get_by_id(self, edit_session_id: str) -> IndependentLectureEditSession | None:
        return self.store.get(edit_session_id)

    async def create(
        self, edit_session: IndependentLectureEditSession
    ) -> IndependentLectureEditSession:
        if not edit_session.started_at:
            edit_session.started_at = datetime.now(timezone.utc)
        self.store[edit_session.id] = edit_session
        return edit_session

    async def update(
        self, edit_session: IndependentLectureEditSession
    ) -> IndependentLectureEditSession:
        self.store[edit_session.id] = edit_session
        return edit_session


@pytest.fixture(autouse=True)
def _patch_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    LECTURE.current_version_id = "ind-version-1"
    LECTURE.status = LectureStatus.READY_FOR_EDIT
    _FakeUserRepo.store = {TEACHER.id: TEACHER}
    _FakeLectureRepo.store = {LECTURE.id: LECTURE}
    _FakeEditSessionRepo.store = {}

    monkeypatch.setattr(
        "app.features.lectures.independent_service.IndependentUserRepository", _FakeUserRepo
    )
    monkeypatch.setattr(
        "app.features.lectures.independent_service.IndependentLectureRepository", _FakeLectureRepo
    )
    monkeypatch.setattr(
        "app.features.lectures.independent_service.IndependentLectureEditSessionRepository",
        _FakeEditSessionRepo,
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
async def test_start_heartbeat_end_roundtrip(client: AsyncClient) -> None:
    start = await client.post(
        "/api/v1/independent/teachers/me/edit-sessions", json={"lecture_id": "ind-lecture-1"}
    )
    assert start.status_code == 201
    session_id = start.json()["data"]["id"]

    heartbeat = await client.post(
        f"/api/v1/independent/teachers/me/edit-sessions/{session_id}/heartbeat",
        json={"active_ms": 20_000, "edits_count": 3, "char_delta": 50},
    )
    assert heartbeat.status_code == 200
    assert heartbeat.json()["data"]["active_ms"] == 20_000

    end = await client.post(
        f"/api/v1/independent/teachers/me/edit-sessions/{session_id}/end",
        json={"active_ms": 25_000, "edits_count": 4, "char_delta": 60},
    )
    assert end.status_code == 200
    assert end.json()["data"]["ended_at"] is not None
