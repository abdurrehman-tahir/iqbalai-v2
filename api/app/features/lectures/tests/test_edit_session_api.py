"""T-133 — effort-tracking edit session API tests (school tenant).

Acceptance (M-10 T-133):
1. Timer pause/resume is a frontend Page Visibility concern — not testable
   at the API layer; covered by the frontend component test instead.
2. 30s heartbeat persists active_ms — test_heartbeat_persists_cumulative_totals.
3. edits_count + char_delta recorded — same test, all three fields.
4. Effort score computed per the locked formula — every *_read response.
5. Effort data available to the scoring pipeline — save_lecture_version links
   edit_session_id -> lecture_version_id (test_save_links_edit_session_to_version).
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
from app.features.lectures.models import (
    LectureStatus,
    SchoolLecture,
    SchoolLectureEditSession,
    SchoolLectureVersion,
)
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
    current_version_id="version-1",
)

V1 = SchoolLectureVersion(
    id="version-1",
    lecture_id="lecture-1",
    version=1,
    body="Original AI-generated body.",
    content_jsonb=None,
    created_at=datetime.now(timezone.utc),
)


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
    created: list[SchoolLectureVersion] = []

    def __init__(self, session: Any) -> None:
        pass

    async def get_by_id(self, version_id: str) -> SchoolLectureVersion | None:
        return self.store.get(version_id)

    async def get_latest_for_lecture(self, lecture_id: str) -> SchoolLectureVersion | None:
        rows = [v for v in self.store.values() if v.lecture_id == lecture_id]
        return max(rows, key=lambda v: v.version) if rows else None

    async def create(self, version: SchoolLectureVersion) -> SchoolLectureVersion:
        if not version.created_at:
            version.created_at = datetime.now(timezone.utc)
        self.store[version.id] = version
        self.__class__.created.append(version)
        return version


class _FakeEditSessionRepo:
    store: dict[str, SchoolLectureEditSession] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def get_by_id(self, edit_session_id: str) -> SchoolLectureEditSession | None:
        return self.store.get(edit_session_id)

    async def create(self, edit_session: SchoolLectureEditSession) -> SchoolLectureEditSession:
        if not edit_session.started_at:
            edit_session.started_at = datetime.now(timezone.utc)
        self.store[edit_session.id] = edit_session
        return edit_session

    async def update(self, edit_session: SchoolLectureEditSession) -> SchoolLectureEditSession:
        self.store[edit_session.id] = edit_session
        return edit_session


class _FakePublish:
    async def __call__(self, *, event_type: str, payload: dict[str, Any]) -> None:
        return None


@pytest.fixture(autouse=True)
def _patch_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    LECTURE.current_version_id = "version-1"
    LECTURE.status = LectureStatus.READY_FOR_EDIT
    _FakeUserRepo.store = {TEACHER.id: TEACHER, OTHER_TEACHER.id: OTHER_TEACHER}
    _FakeLectureRepo.store = {LECTURE.id: LECTURE}
    _FakeVersionRepo.store = {V1.id: V1}
    _FakeVersionRepo.created = []
    _FakeEditSessionRepo.store = {}

    monkeypatch.setattr("app.features.lectures.service.UserRepository", _FakeUserRepo)
    monkeypatch.setattr("app.features.lectures.service.LectureRepository", _FakeLectureRepo)
    monkeypatch.setattr("app.features.lectures.service.LectureVersionRepository", _FakeVersionRepo)
    monkeypatch.setattr(
        "app.features.lectures.service.LectureEditSessionRepository", _FakeEditSessionRepo
    )
    monkeypatch.setattr("app.features.lectures.service.publish_lecture_event", _FakePublish())


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
async def test_start_edit_session_creates_a_session(client: AsyncClient) -> None:
    res = await client.post("/api/v1/teachers/me/edit-sessions", json={"lecture_id": "lecture-1"})
    assert res.status_code == 201
    data = res.json()["data"]
    assert data["active_ms"] == 0
    assert data["edits_count"] == 0
    assert data["char_delta"] == 0
    assert data["ended_at"] is None
    assert data["effort_score"] == 0.0
    assert len(_FakeEditSessionRepo.store) == 1


@pytest.mark.asyncio
async def test_start_edit_session_rejects_unowned_lecture(other_client: AsyncClient) -> None:
    res = await other_client.post(
        "/api/v1/teachers/me/edit-sessions", json={"lecture_id": "lecture-1"}
    )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_heartbeat_persists_cumulative_totals(client: AsyncClient) -> None:
    """Acceptance #2/#3/#4."""
    start = await client.post("/api/v1/teachers/me/edit-sessions", json={"lecture_id": "lecture-1"})
    session_id = start.json()["data"]["id"]

    res = await client.post(
        f"/api/v1/teachers/me/edit-sessions/{session_id}/heartbeat",
        json={"active_ms": 30_000, "edits_count": 5, "char_delta": 120},
    )
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["active_ms"] == 30_000
    assert data["edits_count"] == 5
    assert data["char_delta"] == 120
    assert data["effort_score"] > 0.0


@pytest.mark.asyncio
async def test_heartbeat_is_idempotent_on_retry(client: AsyncClient) -> None:
    """A retried heartbeat with the same cumulative values is a safe no-op —
    not a double-count, since the client sends totals, not deltas.
    """
    start = await client.post("/api/v1/teachers/me/edit-sessions", json={"lecture_id": "lecture-1"})
    session_id = start.json()["data"]["id"]

    payload = {"active_ms": 60_000, "edits_count": 10, "char_delta": 200}
    first = await client.post(
        f"/api/v1/teachers/me/edit-sessions/{session_id}/heartbeat", json=payload
    )
    retried = await client.post(
        f"/api/v1/teachers/me/edit-sessions/{session_id}/heartbeat", json=payload
    )
    assert first.json()["data"]["active_ms"] == retried.json()["data"]["active_ms"] == 60_000


@pytest.mark.asyncio
async def test_heartbeat_rejects_unowned_session(
    client: AsyncClient, other_client: AsyncClient
) -> None:
    start = await client.post("/api/v1/teachers/me/edit-sessions", json={"lecture_id": "lecture-1"})
    session_id = start.json()["data"]["id"]

    res = await other_client.post(
        f"/api/v1/teachers/me/edit-sessions/{session_id}/heartbeat",
        json={"active_ms": 1000, "edits_count": 1, "char_delta": 10},
    )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_end_session_sets_ended_at_and_rejects_further_heartbeats(
    client: AsyncClient,
) -> None:
    start = await client.post("/api/v1/teachers/me/edit-sessions", json={"lecture_id": "lecture-1"})
    session_id = start.json()["data"]["id"]

    end_res = await client.post(
        f"/api/v1/teachers/me/edit-sessions/{session_id}/end",
        json={"active_ms": 90_000, "edits_count": 20, "char_delta": 500},
    )
    assert end_res.status_code == 200
    assert end_res.json()["data"]["ended_at"] is not None

    late_heartbeat = await client.post(
        f"/api/v1/teachers/me/edit-sessions/{session_id}/heartbeat",
        json={"active_ms": 100_000, "edits_count": 21, "char_delta": 510},
    )
    assert late_heartbeat.status_code == 422


@pytest.mark.asyncio
async def test_ending_an_already_ended_session_is_a_safe_no_op(client: AsyncClient) -> None:
    start = await client.post("/api/v1/teachers/me/edit-sessions", json={"lecture_id": "lecture-1"})
    session_id = start.json()["data"]["id"]

    first_end = await client.post(
        f"/api/v1/teachers/me/edit-sessions/{session_id}/end",
        json={"active_ms": 90_000, "edits_count": 20, "char_delta": 500},
    )
    second_end = await client.post(
        f"/api/v1/teachers/me/edit-sessions/{session_id}/end",
        json={"active_ms": 999_999, "edits_count": 999, "char_delta": 9999},
    )
    assert second_end.status_code == 200
    # Second end's payload is ignored — the session was already closed.
    assert second_end.json()["data"]["active_ms"] == first_end.json()["data"]["active_ms"] == 90_000


@pytest.mark.asyncio
async def test_save_links_edit_session_to_version(client: AsyncClient) -> None:
    """Acceptance #5 — effort data becomes discoverable via the resulting version."""
    start = await client.post("/api/v1/teachers/me/edit-sessions", json={"lecture_id": "lecture-1"})
    session_id = start.json()["data"]["id"]
    await client.post(
        f"/api/v1/teachers/me/edit-sessions/{session_id}/heartbeat",
        json={"active_ms": 45_000, "edits_count": 8, "char_delta": 300},
    )

    save_res = await client.post(
        "/api/v1/teachers/me/lectures/lecture-1/versions",
        json={
            "content_jsonb": {
                "type": "doc",
                "content": [
                    {"type": "paragraph", "content": [{"type": "text", "text": "Edited body."}]}
                ],
            },
            "is_autosave": False,
            "edit_session_id": session_id,
        },
    )
    assert save_res.status_code == 200
    new_version_id = save_res.json()["data"]["id"]

    linked_session = _FakeEditSessionRepo.store[session_id]
    assert linked_session.lecture_version_id == new_version_id


@pytest.mark.asyncio
async def test_save_with_unknown_edit_session_id_still_succeeds(client: AsyncClient) -> None:
    """Linking is best-effort — a bad/foreign session id must never block the save."""
    res = await client.post(
        "/api/v1/teachers/me/lectures/lecture-1/versions",
        json={
            "content_jsonb": {
                "type": "doc",
                "content": [{"type": "paragraph", "content": [{"type": "text", "text": "x"}]}],
            },
            "is_autosave": False,
            "edit_session_id": "does-not-exist",
        },
    )
    assert res.status_code == 200
