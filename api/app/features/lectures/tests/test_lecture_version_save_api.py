"""T-130 — save-a-new-immutable-version API tests (school tenant).

Acceptance (M-10 T-130):
1. Manual save creates a new version row.
2. The prior version is untouched (immutable).
3. Auto-save also produces a version (frontend debounces; backend treats it
   the same as a manual save, just tagged ``is_autosave``).
4. ``lecture.version.created`` emitted on each save.
5. Server-validated against teacher ownership (non-owner -> 404, not leaked).
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
from app.features.lectures.tiptap import empty_doc
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

NOT_EDITABLE_LECTURE = SchoolLecture(
    id="lecture-2",
    school_id="school-1",
    teacher_user_id="teacher-1",
    title="Optics",
    topic="Reflection",
    status=LectureStatus.GENERATING,
    current_version_id=None,
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
        if not rows:
            return None
        return max(rows, key=lambda v: v.version)

    async def create(self, version: SchoolLectureVersion) -> SchoolLectureVersion:
        if not version.created_at:
            version.created_at = datetime.now(timezone.utc)
        self.store[version.id] = version
        self.__class__.created.append(version)
        return version


class _PublishSpy:
    calls: list[dict[str, Any]] = []

    async def __call__(self, *, event_type: str, payload: dict[str, Any]) -> None:
        self.__class__.calls.append({"event_type": event_type, "payload": payload})


@pytest.fixture(autouse=True)
def _patch_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    # LECTURE/V1 are shared module-level objects — reset mutations a prior
    # test's save left behind (lecture.current_version_id) before each test.
    LECTURE.current_version_id = "version-1"
    _FakeUserRepo.store = {TEACHER.id: TEACHER, OTHER_TEACHER.id: OTHER_TEACHER}
    _FakeLectureRepo.store = {LECTURE.id: LECTURE, NOT_EDITABLE_LECTURE.id: NOT_EDITABLE_LECTURE}
    _FakeVersionRepo.store = {V1.id: V1}
    _FakeVersionRepo.created = []
    _PublishSpy.calls = []

    monkeypatch.setattr("app.features.lectures.service.UserRepository", _FakeUserRepo)
    monkeypatch.setattr("app.features.lectures.service.LectureRepository", _FakeLectureRepo)
    monkeypatch.setattr("app.features.lectures.service.LectureVersionRepository", _FakeVersionRepo)
    monkeypatch.setattr("app.features.lectures.service.publish_lecture_event", _PublishSpy())


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
async def test_manual_save_creates_new_version(client: AsyncClient) -> None:
    res = await client.post(
        "/api/v1/teachers/me/lectures/lecture-1/versions",
        json={
            "content_jsonb": {
                "type": "doc",
                "content": [
                    {"type": "paragraph", "content": [{"type": "text", "text": "Edited body."}]}
                ],
            },
            "is_autosave": False,
        },
    )
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["version"] == 2
    assert data["body"] == "Edited body."
    assert len(_FakeVersionRepo.created) == 1


@pytest.mark.asyncio
async def test_prior_version_is_untouched(client: AsyncClient) -> None:
    """Acceptance #2 — immutability."""
    original_body = V1.body
    await client.post(
        "/api/v1/teachers/me/lectures/lecture-1/versions",
        json={
            "content_jsonb": {
                "type": "doc",
                "content": [
                    {"type": "paragraph", "content": [{"type": "text", "text": "Edited body."}]}
                ],
            },
            "is_autosave": False,
        },
    )
    assert _FakeVersionRepo.store["version-1"].body == original_body
    assert _FakeVersionRepo.store["version-1"] is V1


@pytest.mark.asyncio
async def test_autosave_also_creates_a_version(client: AsyncClient) -> None:
    """Acceptance #3."""
    res = await client.post(
        "/api/v1/teachers/me/lectures/lecture-1/versions",
        json={
            "content_jsonb": {
                "type": "doc",
                "content": [
                    {"type": "paragraph", "content": [{"type": "text", "text": "Autosaved body."}]}
                ],
            },
            "is_autosave": True,
        },
    )
    assert res.status_code == 200
    assert res.json()["data"]["version"] == 2
    assert len(_FakeVersionRepo.created) == 1


@pytest.mark.asyncio
async def test_save_emits_lecture_version_created_event(client: AsyncClient) -> None:
    """Acceptance #4."""
    await client.post(
        "/api/v1/teachers/me/lectures/lecture-1/versions",
        json={
            "content_jsonb": empty_doc()
            | {"content": [{"type": "paragraph", "content": [{"type": "text", "text": "x"}]}]},
            "is_autosave": False,
        },
    )
    assert len(_PublishSpy.calls) == 1
    call = _PublishSpy.calls[0]
    assert call["event_type"] == "lecture.version.created"
    assert call["payload"]["lecture_id"] == "lecture-1"
    assert call["payload"]["version"] == 2
    assert call["payload"]["tenant_type"] == "school"


@pytest.mark.asyncio
async def test_non_owner_teacher_gets_not_found(other_client: AsyncClient) -> None:
    """Acceptance #5 — ownership check; a non-owner never learns the lecture exists."""
    res = await other_client.post(
        "/api/v1/teachers/me/lectures/lecture-1/versions",
        json={"content_jsonb": {"type": "doc", "content": []}, "is_autosave": False},
    )
    assert res.status_code == 404
    assert len(_FakeVersionRepo.created) == 0


@pytest.mark.asyncio
async def test_save_rejected_when_lecture_not_in_editable_status(client: AsyncClient) -> None:
    res = await client.post(
        "/api/v1/teachers/me/lectures/lecture-2/versions",
        json={"content_jsonb": {"type": "doc", "content": []}, "is_autosave": False},
    )
    assert res.status_code == 422
    assert len(_FakeVersionRepo.created) == 0


@pytest.mark.asyncio
async def test_save_rejects_empty_content(client: AsyncClient) -> None:
    res = await client.post(
        "/api/v1/teachers/me/lectures/lecture-1/versions",
        json={"content_jsonb": {"type": "doc", "content": []}, "is_autosave": False},
    )
    assert res.status_code == 422
    assert len(_FakeVersionRepo.created) == 0


@pytest.mark.asyncio
async def test_get_current_version_returns_content(client: AsyncClient) -> None:
    res = await client.get("/api/v1/teachers/me/lectures/lecture-1/versions/current")
    assert res.status_code == 200
    assert res.json()["data"]["id"] == "version-1"
    assert res.json()["data"]["body"] == "Original AI-generated body."
