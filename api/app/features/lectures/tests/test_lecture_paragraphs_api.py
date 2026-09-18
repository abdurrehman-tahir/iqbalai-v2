"""Lecture paragraphs + source-attribution API tests — T-118."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.v1.router import router as v1_router
from app.core.dependencies import get_current_user, get_db
from app.core.exceptions import setup_exception_handlers
from app.features.lectures.models import LectureStatus, SchoolLecture, SchoolLectureParagraph
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

LECTURE_READY = SchoolLecture(
    id="lec-1",
    school_id="school-1",
    teacher_user_id="teacher-1",
    title="Newton's Laws",
    topic="Newton's Laws",
    status=LectureStatus.READY_FOR_EDIT,
    current_version_id="ver-1",
)

LECTURE_STILL_GENERATING = SchoolLecture(
    id="lec-2",
    school_id="school-1",
    teacher_user_id="teacher-1",
    title="Forces",
    topic="Forces",
    status=LectureStatus.GENERATING,
    current_version_id=None,
)

PARAGRAPHS = [
    SchoolLectureParagraph(
        id="para-1",
        lecture_version_id="ver-1",
        ordinal=0,
        text="Newton's first law of motion...",
        source_metadata_jsonb={"tier": "curriculum", "chunk_id": "chunk-c"},
    ),
    SchoolLectureParagraph(
        id="para-2",
        lecture_version_id="ver-1",
        ordinal=1,
        text="For example, a bus braking suddenly...",
        source_metadata_jsonb={
            "tier": "reference",
            "book_name": "Physics Today",
            "chunk_id": "chunk-r",
        },
    ),
    SchoolLectureParagraph(
        id="para-3",
        lecture_version_id="ver-1",
        ordinal=2,
        text="This concept extends to rotational systems as well.",
        source_metadata_jsonb={"tier": "ai_knowledge"},
    ),
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


class _FakeParagraphRepo:
    by_version: dict[str, list[SchoolLectureParagraph]] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def list_by_version(self, lecture_version_id: str) -> list[SchoolLectureParagraph]:
        return sorted(self.by_version.get(lecture_version_id, []), key=lambda p: p.ordinal)


@pytest.fixture(autouse=True)
def _patch_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    _FakeUserRepo.store = {TEACHER.id: TEACHER, OTHER_TEACHER.id: OTHER_TEACHER}
    _FakeLectureRepo.store = {
        LECTURE_READY.id: LECTURE_READY,
        LECTURE_STILL_GENERATING.id: LECTURE_STILL_GENERATING,
    }
    _FakeParagraphRepo.by_version = {"ver-1": PARAGRAPHS}
    monkeypatch.setattr("app.features.lectures.service.UserRepository", _FakeUserRepo)
    monkeypatch.setattr("app.features.lectures.service.LectureRepository", _FakeLectureRepo)
    monkeypatch.setattr(
        "app.features.lectures.service.LectureParagraphRepository", _FakeParagraphRepo
    )


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
async def test_lists_paragraphs_with_source_tiers() -> None:
    async with _make_client(_fake_user) as client:
        res = await client.get("/api/v1/teachers/me/lectures/lec-1/paragraphs")

    assert res.status_code == 200
    data = res.json()["data"]
    assert len(data) == 3
    assert data[0]["tier"] == "curriculum"
    assert data[0]["book_name"] is None
    assert data[1]["tier"] == "reference"
    assert data[1]["book_name"] == "Physics Today"
    assert data[2]["tier"] == "ai_knowledge"
    # Paragraph order is preserved and chunk_id is not leaked to the client.
    assert [p["ordinal"] for p in data] == [0, 1, 2]
    assert "chunk_id" not in data[0]


@pytest.mark.asyncio
async def test_returns_empty_list_before_first_version_persisted() -> None:
    async with _make_client(_fake_user) as client:
        res = await client.get("/api/v1/teachers/me/lectures/lec-2/paragraphs")

    assert res.status_code == 200
    assert res.json()["data"] == []


@pytest.mark.asyncio
async def test_non_owning_teacher_cannot_read_paragraphs() -> None:
    async with _make_client(_fake_other_user) as client:
        res = await client.get("/api/v1/teachers/me/lectures/lec-1/paragraphs")

    assert res.status_code == 404


@pytest.mark.asyncio
async def test_unknown_lecture_returns_404() -> None:
    async with _make_client(_fake_user) as client:
        res = await client.get("/api/v1/teachers/me/lectures/does-not-exist/paragraphs")

    assert res.status_code == 404
