"""Independent teacher stripped-variant wizard API tests — T-125."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.v1.router import router as v1_router
from app.core.dependencies import get_current_user, get_db
from app.core.exceptions import setup_exception_handlers
from app.features.independent_users.models import (
    IndependentUser,
    IndependentUserAccountStatus,
    IndependentUserRole,
)
from app.features.lectures.models import (
    IndependentLecture,
    IndependentLectureDraft,
    IndependentLectureParagraph,
    LectureStatus,
)
from app.features.library.independent_personal_models import (
    IndependentPersonalContent,
    PersonalContentStatus,
    PersonalContentType,
)

TEACHER = IndependentUser(
    id="teacher-1",
    authentik_id="auth-teacher",
    email="teacher@example.com",
    display_name="Teacher One",
    role=IndependentUserRole.INDEPENDENT_TEACHER,
    status=IndependentUserAccountStatus.ACTIVE,
)
OTHER_TEACHER = IndependentUser(
    id="teacher-2",
    authentik_id="auth-teacher-2",
    email="teacher2@example.com",
    display_name="Teacher Two",
    role=IndependentUserRole.INDEPENDENT_TEACHER,
    status=IndependentUserAccountStatus.ACTIVE,
)

REFERENCE_AVAILABLE = IndependentPersonalContent(
    id="ref-1",
    user_id="teacher-1",
    content_type=PersonalContentType.REFERENCE,
    title="My Physics Notes",
    file_key="k1",
    file_sha256="a" * 64,
    status=PersonalContentStatus.AVAILABLE,
    vector_collection="independent_personal_teacher-1",
)
REFERENCE_PENDING = IndependentPersonalContent(
    id="ref-2",
    user_id="teacher-1",
    content_type=PersonalContentType.REFERENCE,
    title="Still Ingesting",
    file_key="k2",
    file_sha256="b" * 64,
    status=PersonalContentStatus.PENDING,
    vector_collection="independent_personal_teacher-1",
)
CURRICULUM_ITEM = IndependentPersonalContent(
    id="curr-1",
    user_id="teacher-1",
    content_type=PersonalContentType.CURRICULUM,
    title="A Curriculum Doc",
    file_key="k3",
    file_sha256="c" * 64,
    status=PersonalContentStatus.AVAILABLE,
    vector_collection="independent_personal_teacher-1",
)

LECTURE_READY = IndependentLecture(
    id="lec-1",
    teacher_user_id="teacher-1",
    title="Newton's Laws",
    topic="Newton's Laws",
    status=LectureStatus.READY_FOR_EDIT,
    current_version_id="ver-1",
)
LECTURE_GENERATING = IndependentLecture(
    id="lec-2",
    teacher_user_id="teacher-1",
    title="Photosynthesis",
    topic="Photosynthesis",
    status=LectureStatus.GENERATING,
    current_version_id=None,
)

PARAGRAPHS = [
    IndependentLectureParagraph(
        id="para-1",
        lecture_version_id="ver-1",
        ordinal=0,
        text="Newton's first law...",
        source_metadata_jsonb={"tier": "reference", "book_name": "My Physics Notes"},
    ),
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

    async def create(self, lecture: IndependentLecture) -> IndependentLecture:
        self.store[lecture.id] = lecture
        return lecture

    async def get_by_id(self, lecture_id: str) -> IndependentLecture | None:
        return self.store.get(lecture_id)


class _FakeParagraphRepo:
    by_version: dict[str, list[IndependentLectureParagraph]] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def list_by_version(self, lecture_version_id: str) -> list[IndependentLectureParagraph]:
        return sorted(self.by_version.get(lecture_version_id, []), key=lambda p: p.ordinal)


class _FakeDraftRepo:
    store: dict[str, IndependentLectureDraft] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def get_active_for_teacher(self, teacher_user_id: str) -> IndependentLectureDraft | None:
        return next((d for d in self.store.values() if d.teacher_user_id == teacher_user_id), None)

    async def create(self, draft: IndependentLectureDraft) -> IndependentLectureDraft:
        self.store[draft.id] = draft
        return draft

    async def update(self, draft: IndependentLectureDraft) -> IndependentLectureDraft:
        return draft

    async def soft_delete(self, draft: IndependentLectureDraft) -> None:
        self.store.pop(draft.id, None)


class _FakePersonalContentRepo:
    store: dict[str, IndependentPersonalContent] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def list_for_user(
        self, user_id: str, *, limit: int = 50, offset: int = 0, content_type: str | None = None
    ) -> list[IndependentPersonalContent]:
        items = [item for item in self.store.values() if item.user_id == user_id]
        if content_type is not None:
            items = [item for item in items if item.content_type.value == content_type]
        return items

    async def get_by_id(self, content_id: str) -> IndependentPersonalContent | None:
        return self.store.get(content_id)


_AUDIT_CALLS: list[dict[str, Any]] = []


@pytest.fixture(autouse=True)
def _patch_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    _FakeUserRepo.store = {TEACHER.id: TEACHER, OTHER_TEACHER.id: OTHER_TEACHER}
    _FakeLectureRepo.store = {
        LECTURE_READY.id: LECTURE_READY,
        LECTURE_GENERATING.id: LECTURE_GENERATING,
    }
    _FakeParagraphRepo.by_version = {"ver-1": PARAGRAPHS}
    _FakeDraftRepo.store = {}
    _FakePersonalContentRepo.store = {
        REFERENCE_AVAILABLE.id: REFERENCE_AVAILABLE,
        REFERENCE_PENDING.id: REFERENCE_PENDING,
        CURRICULUM_ITEM.id: CURRICULUM_ITEM,
    }
    monkeypatch.setattr(
        "app.features.lectures.independent_service.IndependentUserRepository", _FakeUserRepo
    )
    monkeypatch.setattr(
        "app.features.lectures.independent_service.IndependentLectureRepository",
        _FakeLectureRepo,
    )
    monkeypatch.setattr(
        "app.features.lectures.independent_service.IndependentLectureParagraphRepository",
        _FakeParagraphRepo,
    )
    monkeypatch.setattr(
        "app.features.lectures.independent_service.IndependentLectureDraftRepository",
        _FakeDraftRepo,
    )
    monkeypatch.setattr(
        "app.features.lectures.independent_service.IndependentPersonalContentRepository",
        _FakePersonalContentRepo,
    )
    monkeypatch.setattr(
        "app.features.lectures.independent_tasks.generate_independent_lecture.apply_async",
        MagicMock(),
    )

    _AUDIT_CALLS.clear()

    async def _spy_audit(**kwargs: Any) -> None:
        _AUDIT_CALLS.append(kwargs)

    monkeypatch.setattr("app.features.lectures.independent_service.audit", _spy_audit)


async def _fake_db() -> AsyncGenerator[None, None]:
    yield None


async def _fake_user() -> dict[str, object]:
    return {"sub": "auth-teacher", "role": "independent_teacher", "user_id": "teacher-1"}


async def _fake_other_user() -> dict[str, object]:
    return {"sub": "auth-teacher-2", "role": "independent_teacher", "user_id": "teacher-2"}


def _make_client(user_dep: Any) -> AsyncClient:
    app = FastAPI()
    setup_exception_handlers(app)
    app.include_router(v1_router, prefix="/api/v1")
    app.dependency_overrides[get_db] = _fake_db
    app.dependency_overrides[get_current_user] = user_dep
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.mark.asyncio
async def test_lists_only_available_references_no_curriculum() -> None:
    """Acceptance #1/#2: Step 3 shows only the teacher's own available references."""
    async with _make_client(_fake_user) as client:
        res = await client.get("/api/v1/independent/teachers/me/lecture-wizard/references")

    assert res.status_code == 200
    data = res.json()["data"]
    assert len(data) == 1
    assert data[0]["id"] == "ref-1"
    assert data[0]["title"] == "My Physics Notes"


@pytest.mark.asyncio
async def test_draft_round_trip_no_grade_scoping() -> None:
    """Acceptance #3: no Grade-Subject scoping in the draft payload."""
    async with _make_client(_fake_user) as client:
        empty = await client.get("/api/v1/independent/teachers/me/lecture-draft")
        assert empty.json()["data"]["data"] == {}

        saved = await client.put(
            "/api/v1/independent/teachers/me/lecture-draft",
            json={
                "step": 1,
                "data": {"topic": "Newton's Laws", "reference_content_ids": ["ref-1"]},
            },
        )

    assert saved.status_code == 200
    assert saved.json()["data"]["data"]["topic"] == "Newton's Laws"


@pytest.mark.asyncio
async def test_generate_creates_lecture_and_enqueues_task() -> None:
    async with _make_client(_fake_user) as client:
        res = await client.post(
            "/api/v1/independent/teachers/me/lecture-wizard/generate",
            json={
                "topic": "Newton's Laws",
                "reference_content_ids": ["ref-1"],
                "teaching_mode": "auto",
            },
        )

    assert res.status_code == 200
    data = res.json()["data"]
    assert data["status"] == "generating"
    assert data["lecture_id"] in _FakeLectureRepo.store
    # T-126: creating the lecture is audit-logged (Acceptance #3), school_id=None.
    from app.features.audit.actions import LECTURE_CREATED

    created_calls = [c for c in _AUDIT_CALLS if c["action"] == LECTURE_CREATED]
    assert created_calls
    assert created_calls[0]["school_id"] is None


@pytest.mark.asyncio
async def test_generate_rejects_reference_not_owned_by_teacher() -> None:
    async with _make_client(_fake_user) as client:
        res = await client.post(
            "/api/v1/independent/teachers/me/lecture-wizard/generate",
            json={
                "topic": "Newton's Laws",
                "reference_content_ids": ["does-not-exist"],
                "teaching_mode": "auto",
            },
        )

    assert res.status_code == 404


@pytest.mark.asyncio
async def test_get_lecture_status_for_polling() -> None:
    async with _make_client(_fake_user) as client:
        res = await client.get("/api/v1/independent/teachers/me/lectures/lec-2")

    assert res.status_code == 200
    data = res.json()["data"]
    assert data["status"] == "generating"
    assert data["current_version_id"] is None


@pytest.mark.asyncio
async def test_lists_paragraphs_with_source_tiers() -> None:
    async with _make_client(_fake_user) as client:
        res = await client.get("/api/v1/independent/teachers/me/lectures/lec-1/paragraphs")

    assert res.status_code == 200
    data = res.json()["data"]
    assert len(data) == 1
    assert data[0]["tier"] == "reference"
    assert data[0]["book_name"] == "My Physics Notes"


@pytest.mark.asyncio
async def test_non_owning_teacher_cannot_read_lecture() -> None:
    async with _make_client(_fake_other_user) as client:
        res = await client.get("/api/v1/independent/teachers/me/lectures/lec-1")

    assert res.status_code == 404


@pytest.mark.asyncio
async def test_unknown_authentik_id_cannot_use_independent_endpoints() -> None:
    """Cross-tenant access -> 404, per ARCH §3.16 ("School user attempting to
    read any independent data -> 404"). A school-tenant JWT's `sub` simply
    never resolves to a row in the independent users table, regardless of
    its `role` claim (require_role treats teacher/independent_teacher as
    peer-level roles, so the router-level gate alone doesn't reject it —
    the service-layer lookup is the real tenant boundary here)."""

    async def _fake_unrelated_user() -> dict[str, object]:
        return {"sub": "not-an-independent-user", "role": "teacher", "user_id": "someone-else"}

    async with _make_client(_fake_unrelated_user) as client:
        res = await client.get("/api/v1/independent/teachers/me/lecture-wizard/references")

    assert res.status_code == 404
