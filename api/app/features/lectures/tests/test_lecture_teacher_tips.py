"""Teacher delivery tips / technique demo / real-world examples — T-124, #28, #41.

Covers the second, separate LLM call (``run_teacher_tips_generation``), its
Celery task wrapper's never-fail-the-lecture contract, and the teacher-facing
read API.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.v1.router import router as v1_router
from app.core.dependencies import get_current_user, get_db
from app.core.exceptions import setup_exception_handlers
from app.features.grades.models import Grade, GradeStatus
from app.features.lectures.generation import run_teacher_tips_generation
from app.features.lectures.models import (
    LectureStatus,
    SchoolLecture,
    SchoolLectureVersion,
)
from app.features.lectures.tasks import generate_lecture_teacher_tips
from app.features.offerings.models import GradeSubjectOffering, OfferingStatus
from app.features.subjects.models import Subject
from app.features.users.models import User, UserAccountStatus, UserRole

# --- run_teacher_tips_generation (generation.py) ----------------------------


def _fake_lecture() -> SchoolLecture:
    return SchoolLecture(
        id="lec-1",
        school_id="school-1",
        grade_subject_offering_id="off-1",
        teacher_user_id="teacher-1",
        title="Newton's Laws",
        topic="Newton's Laws",
        status=LectureStatus.READY_FOR_EDIT,
        current_version_id="ver-1",
    )


def _fake_version() -> SchoolLectureVersion:
    return SchoolLectureVersion(
        id="ver-1",
        lecture_id="lec-1",
        version=1,
        body="Newton's first law...",
        teacher_tips_jsonb=None,
    )


def _fake_session(lecture: SchoolLecture, version: SchoolLectureVersion) -> AsyncMock:
    offering = GradeSubjectOffering(
        id="off-1",
        school_id="school-1",
        grade_id="grade-9",
        subject_id="subj-physics",
        assigned_teacher_id="teacher-1",
        academic_session="2025-2026",
        status=OfferingStatus.ACTIVE,
    )
    subject = Subject(id="subj-physics", school_id="school-1", name="Physics")
    grade = Grade(
        id="grade-9",
        school_id="school-1",
        name="Grade 9",
        academic_session="2025-2026",
        level_ordinal=9,
        status=GradeStatus.ACTIVE,
    )

    session = AsyncMock()

    async def _get(model: type[Any], pk: str) -> Any:
        if model is SchoolLecture and pk == "lec-1":
            return lecture
        if model is SchoolLectureVersion and pk == "ver-1":
            return version
        if model is GradeSubjectOffering and pk == "off-1":
            return offering
        if model is Subject and pk == "subj-physics":
            return subject
        if model is Grade and pk == "grade-9":
            return grade
        return None

    session.get = AsyncMock(side_effect=_get)
    session.commit = AsyncMock()
    return session


@pytest.mark.asyncio
async def test_run_teacher_tips_generation_persists_tips(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lecture = _fake_lecture()
    version = _fake_version()
    session = _fake_session(lecture, version)

    async def _fake_chat(*_a: Any, **_k: Any) -> str:
        return (
            '{"delivery_tips": ["Tip 1", "Tip 2", "Tip 3"], '
            '"technique_demo": "Ask a guiding question.", '
            '"real_world_examples": ['
            '{"title": "Seatbelts", "text": "Inertia keeps you moving."}, '
            '{"title": "Rockets", "text": "Action-reaction propels a rocket."}'
            "]}"
        )

    monkeypatch.setattr("app.features.lectures.generation.chat", _fake_chat)

    await run_teacher_tips_generation(
        session,
        lecture_id="lec-1",
        school_id="school-1",
        version_id="ver-1",
        topic="Newton's Laws",
        target_language="en",
    )

    assert version.teacher_tips_jsonb is not None
    stored = version.teacher_tips_jsonb
    assert stored["delivery_tips"] == ["Tip 1", "Tip 2", "Tip 3"]
    assert stored["technique_demo"] == "Ask a guiding question."
    examples = stored["real_world_examples"]
    assert isinstance(examples, list)
    assert len(examples) == 2
    assert stored["language"] == "en"
    session.commit.assert_awaited()


@pytest.mark.asyncio
async def test_run_teacher_tips_generation_swallows_llm_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Supplementary content: an LLM failure must not raise or touch the lecture."""
    lecture = _fake_lecture()
    version = _fake_version()
    session = _fake_session(lecture, version)

    async def _raising_chat(*_a: Any, **_k: Any) -> str:
        raise RuntimeError("LLM provider down")

    monkeypatch.setattr("app.features.lectures.generation.chat", _raising_chat)

    await run_teacher_tips_generation(
        session,
        lecture_id="lec-1",
        school_id="school-1",
        version_id="ver-1",
        topic="Newton's Laws",
        target_language="en",
    )

    assert version.teacher_tips_jsonb is None
    session.commit.assert_not_awaited()
    assert lecture.status == LectureStatus.READY_FOR_EDIT


@pytest.mark.asyncio
async def test_run_teacher_tips_generation_swallows_malformed_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lecture = _fake_lecture()
    version = _fake_version()
    session = _fake_session(lecture, version)

    async def _fake_chat(*_a: Any, **_k: Any) -> str:
        return "not valid json"

    monkeypatch.setattr("app.features.lectures.generation.chat", _fake_chat)

    await run_teacher_tips_generation(
        session,
        lecture_id="lec-1",
        school_id="school-1",
        version_id="ver-1",
        topic="Newton's Laws",
        target_language="en",
    )

    assert version.teacher_tips_jsonb is None


@pytest.mark.asyncio
async def test_run_teacher_tips_generation_noop_without_offering(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A lecture with no Grade-Subject offering has nothing to describe — no-op."""
    lecture = SchoolLecture(
        id="lec-2",
        school_id="school-1",
        grade_subject_offering_id=None,
        teacher_user_id="teacher-1",
        title="Untitled",
        topic="Untitled",
        status=LectureStatus.READY_FOR_EDIT,
        current_version_id="ver-2",
    )
    version = SchoolLectureVersion(
        id="ver-2", lecture_id="lec-2", version=1, body="...", teacher_tips_jsonb=None
    )
    session = AsyncMock()

    async def _get(model: type[Any], pk: str) -> Any:
        if model is SchoolLecture and pk == "lec-2":
            return lecture
        if model is SchoolLectureVersion and pk == "ver-2":
            return version
        return None

    session.get = AsyncMock(side_effect=_get)
    session.commit = AsyncMock()

    chat_called = False

    async def _fake_chat(*_a: Any, **_k: Any) -> str:
        nonlocal chat_called
        chat_called = True
        return "{}"

    monkeypatch.setattr("app.features.lectures.generation.chat", _fake_chat)

    await run_teacher_tips_generation(
        session,
        lecture_id="lec-2",
        school_id="school-1",
        version_id="ver-2",
        topic="Untitled",
        target_language="en",
    )

    assert chat_called is False
    assert version.teacher_tips_jsonb is None


# --- generate_lecture_teacher_tips Celery task (tasks.py) -------------------

_TASK_KWARGS: dict[str, Any] = {
    "lecture_id": "lec-1",
    "school_id": "school-1",
    "version_id": "ver-1",
    "topic": "Newton's Laws",
}


def test_task_success_path() -> None:
    with patch("app.features.lectures.tasks.run_db") as mock_run_db:
        result = generate_lecture_teacher_tips.run(**_TASK_KWARGS)

    assert result == {"lecture_id": "lec-1", "version_id": "ver-1", "status": "ready"}
    mock_run_db.assert_called_once()


def test_task_never_raises_on_failure() -> None:
    """The whole point of a separate task: a tips failure must not fail the caller."""
    with patch("app.features.lectures.tasks.run_db", side_effect=RuntimeError("boom")):
        result = generate_lecture_teacher_tips.run(**_TASK_KWARGS)

    assert result == {"lecture_id": "lec-1", "version_id": "ver-1", "status": "failed"}


# --- GET /teachers/me/lectures/{lecture_id}/teacher-tips (API) -------------

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

LECTURE_NO_VERSION = SchoolLecture(
    id="lec-pending",
    school_id="school-1",
    teacher_user_id="teacher-1",
    title="Still Generating",
    topic="Still Generating",
    status=LectureStatus.GENERATING,
    current_version_id=None,
)
LECTURE_WITH_TIPS = SchoolLecture(
    id="lec-ready",
    school_id="school-1",
    teacher_user_id="teacher-1",
    title="Newton's Laws",
    topic="Newton's Laws",
    status=LectureStatus.READY_FOR_EDIT,
    current_version_id="ver-ready",
)
VERSION_WITH_TIPS = SchoolLectureVersion(
    id="ver-ready",
    lecture_id="lec-ready",
    version=1,
    body="...",
    teacher_tips_jsonb={
        "delivery_tips": ["Use a real object to demonstrate inertia."],
        "technique_demo": "Push a book across the table.",
        "real_world_examples": [
            {"title": "Seatbelts", "text": "Inertia keeps you moving in a crash."},
            {"title": "Rockets", "text": "Action-reaction propels a rocket."},
        ],
        "language": "en",
    },
)
LECTURE_TIPS_NOT_YET_READY = SchoolLecture(
    id="lec-nogen",
    school_id="school-1",
    teacher_user_id="teacher-1",
    title="No Tips Yet",
    topic="No Tips Yet",
    status=LectureStatus.READY_FOR_EDIT,
    current_version_id="ver-nogen",
)
VERSION_NO_TIPS = SchoolLectureVersion(
    id="ver-nogen", lecture_id="lec-nogen", version=1, body="...", teacher_tips_jsonb=None
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

    def __init__(self, session: Any) -> None:
        pass

    async def get_by_id(self, version_id: str) -> SchoolLectureVersion | None:
        return self.store.get(version_id)


@pytest.fixture(autouse=True)
def _patch_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    _FakeUserRepo.store = {TEACHER.id: TEACHER, OTHER_TEACHER.id: OTHER_TEACHER}
    _FakeLectureRepo.store = {
        LECTURE_NO_VERSION.id: LECTURE_NO_VERSION,
        LECTURE_WITH_TIPS.id: LECTURE_WITH_TIPS,
        LECTURE_TIPS_NOT_YET_READY.id: LECTURE_TIPS_NOT_YET_READY,
    }
    _FakeVersionRepo.store = {
        VERSION_WITH_TIPS.id: VERSION_WITH_TIPS,
        VERSION_NO_TIPS.id: VERSION_NO_TIPS,
    }
    monkeypatch.setattr("app.features.lectures.service.UserRepository", _FakeUserRepo)
    monkeypatch.setattr("app.features.lectures.service.LectureRepository", _FakeLectureRepo)
    monkeypatch.setattr("app.features.lectures.service.LectureVersionRepository", _FakeVersionRepo)


async def _fake_db() -> AsyncGenerator[None, None]:
    yield None


async def _fake_user() -> dict[str, object]:
    return {"sub": "auth-teacher", "role": "teacher", "user_id": "teacher-1"}


async def _fake_other_user() -> dict[str, object]:
    return {"sub": "auth-teacher-2", "role": "teacher", "user_id": "teacher-2"}


def _make_client(user_dep: Any) -> AsyncClient:
    app = FastAPI()
    setup_exception_handlers(app)
    app.include_router(v1_router, prefix="/api/v1")
    app.dependency_overrides[get_db] = _fake_db
    app.dependency_overrides[get_current_user] = user_dep
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.mark.asyncio
async def test_pending_before_first_version_persisted() -> None:
    async with _make_client(_fake_user) as client:
        res = await client.get("/api/v1/teachers/me/lectures/lec-pending/teacher-tips")

    assert res.status_code == 200
    data = res.json()["data"]
    assert data["status"] == "pending"
    assert data["tips"] is None


@pytest.mark.asyncio
async def test_pending_when_version_exists_but_tips_not_generated_yet() -> None:
    async with _make_client(_fake_user) as client:
        res = await client.get("/api/v1/teachers/me/lectures/lec-nogen/teacher-tips")

    assert res.status_code == 200
    assert res.json()["data"]["status"] == "pending"


@pytest.mark.asyncio
async def test_ready_returns_tips_content() -> None:
    async with _make_client(_fake_user) as client:
        res = await client.get("/api/v1/teachers/me/lectures/lec-ready/teacher-tips")

    assert res.status_code == 200
    data = res.json()["data"]
    assert data["status"] == "ready"
    assert data["tips"]["technique_demo"] == "Push a book across the table."
    assert len(data["tips"]["delivery_tips"]) == 1
    assert len(data["tips"]["real_world_examples"]) == 2


@pytest.mark.asyncio
async def test_non_owning_teacher_cannot_read_tips() -> None:
    async with _make_client(_fake_other_user) as client:
        res = await client.get("/api/v1/teachers/me/lectures/lec-ready/teacher-tips")

    assert res.status_code == 404
