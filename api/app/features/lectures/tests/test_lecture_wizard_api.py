"""Lecture wizard API tests — T-114."""

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
from app.features.grades.models import Grade, GradeStatus
from app.features.lectures.models import SchoolLectureDraft
from app.features.lectures.service import flatten_topic_tree
from app.features.library.school_models import (
    LibraryContentType,
    LibraryIngestionStatus,
    LibraryVisibility,
    SchoolLibraryItem,
)
from app.features.offerings.models import GradeSubjectOffering, OfferingStatus
from app.features.subjects.models import Subject, SubjectStatus
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

OFFERING = GradeSubjectOffering(
    id="offering-1",
    school_id="school-1",
    grade_id="grade-1",
    subject_id="subj-1",
    assigned_teacher_id="teacher-1",
    academic_session="2025-2026",
    status=OfferingStatus.ACTIVE,
)

GRADE = Grade(
    id="grade-1",
    school_id="school-1",
    name="Grade 9",
    academic_session="2025-2026",
    level_ordinal=9,
    status=GradeStatus.ACTIVE,
)

SUBJECT = Subject(
    id="subj-1",
    school_id="school-1",
    name="Physics",
    language="en",
    status=SubjectStatus.ACTIVE,
)

CURRICULUM = SchoolLibraryItem(
    id="curr-1",
    school_id="school-1",
    title="Punjab Physics 9",
    content_type=LibraryContentType.CURRICULUM,
    language="en",
    subject_id="subj-1",
    grade_level_ordinal=9,
    storage_key="k",
    sha256="a" * 64,
    ingestion_status=LibraryIngestionStatus.AVAILABLE,
    topic_tree_jsonb={
        "chapters": [
            {
                "title": "Mechanics",
                "sections": [
                    {"title": "Newton", "sub_topics": ["Third law", "First law"]},
                ],
            }
        ],
        "parse_degraded": False,
    },
    created_by="teacher-1",
    visibility=LibraryVisibility.SCHOOL_PUBLIC,
)


class _FakeUserRepo:
    store: dict[str, User] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def get_by_authentik_id(self, authentik_id: str) -> User | None:
        return next((u for u in self.store.values() if u.authentik_id == authentik_id), None)


class _FakeOfferingRepo:
    store: dict[str, GradeSubjectOffering] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def list_by_teacher(self, teacher_id: str) -> list[GradeSubjectOffering]:
        return [
            o
            for o in self.store.values()
            if o.assigned_teacher_id == teacher_id and o.deleted_at is None
        ]

    async def get_by_id(self, id: str) -> GradeSubjectOffering | None:
        return self.store.get(id)


class _FakeGradeRepo:
    store: dict[str, Grade] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def get_by_id(self, id: str) -> Grade | None:
        return self.store.get(id)


class _FakeSubjectRepo:
    store: dict[str, Subject] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def get_by_id(self, id: str) -> Subject | None:
        return self.store.get(id)


class _FakeLibraryRepo:
    items: dict[str, SchoolLibraryItem] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def list_for_user(self, **kwargs: Any) -> tuple[list[SchoolLibraryItem], int]:
        rows = list(self.items.values())
        return rows, len(rows)

    async def get_by_id(self, item_id: str) -> SchoolLibraryItem | None:
        return self.items.get(item_id)

    async def get_selection(self, library_item_id: str, user_id: str) -> None:
        return None


class _FakeDraftRepo:
    store: dict[str, SchoolLectureDraft] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def get_active_for_teacher(self, teacher_user_id: str) -> SchoolLectureDraft | None:
        for d in self.store.values():
            if d.teacher_user_id == teacher_user_id and d.deleted_at is None:
                return d
        return None

    async def create(self, draft: SchoolLectureDraft) -> SchoolLectureDraft:
        if not draft.updated_at:
            draft.updated_at = datetime.now(timezone.utc)
        if not draft.created_at:
            draft.created_at = datetime.now(timezone.utc)
        self.store[draft.id] = draft
        return draft

    async def update(self, draft: SchoolLectureDraft) -> SchoolLectureDraft:
        draft.updated_at = datetime.now(timezone.utc)
        self.store[draft.id] = draft
        return draft


@pytest.fixture(autouse=True)
def _patch_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    _FakeUserRepo.store = {TEACHER.id: TEACHER}
    _FakeOfferingRepo.store = {OFFERING.id: OFFERING}
    _FakeGradeRepo.store = {GRADE.id: GRADE}
    _FakeSubjectRepo.store = {SUBJECT.id: SUBJECT}
    _FakeLibraryRepo.items = {CURRICULUM.id: CURRICULUM}
    _FakeDraftRepo.store = {}
    monkeypatch.setattr("app.features.lectures.service.UserRepository", _FakeUserRepo)
    monkeypatch.setattr("app.features.lectures.service.OfferingRepository", _FakeOfferingRepo)
    monkeypatch.setattr("app.features.lectures.service.GradeRepository", _FakeGradeRepo)
    monkeypatch.setattr("app.features.lectures.service.SubjectRepository", _FakeSubjectRepo)
    monkeypatch.setattr("app.features.lectures.service.SchoolLibraryRepository", _FakeLibraryRepo)
    monkeypatch.setattr("app.features.lectures.service.LectureDraftRepository", _FakeDraftRepo)


async def _fake_db() -> AsyncGenerator[None, None]:
    yield None


async def _fake_user() -> dict[str, object]:
    return {"sub": "auth-teacher", "role": "teacher", "user_id": "teacher-1"}


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


def test_flatten_topic_tree() -> None:
    tree = CURRICULUM.topic_tree_jsonb
    assert isinstance(tree, dict)
    topics = flatten_topic_tree(tree)
    assert len(topics) == 2
    assert topics[0].label == "Third law"
    assert "Mechanics > Newton > Third law" == topics[0].path


@pytest.mark.asyncio
async def test_list_my_offerings(client: AsyncClient) -> None:
    res = await client.get("/api/v1/teachers/me/offerings")
    assert res.status_code == 200
    data = res.json()["data"]
    assert len(data) == 1
    assert data[0]["id"] == "offering-1"
    assert data[0]["subject_name"] == "Physics"
    assert data[0]["grade_level_ordinal"] == 9


@pytest.mark.asyncio
async def test_list_curricula_marks_primary(client: AsyncClient) -> None:
    res = await client.get(
        "/api/v1/teachers/me/lecture-wizard/curricula",
        params={"grade_subject_offering_id": "offering-1"},
    )
    assert res.status_code == 200
    data = res.json()["data"]
    assert len(data) == 1
    assert data[0]["is_primary"] is True
    assert data[0]["parse_degraded"] is False


@pytest.mark.asyncio
async def test_list_topics(client: AsyncClient) -> None:
    res = await client.get(
        "/api/v1/teachers/me/lecture-wizard/topics",
        params={
            "curriculum_id": "curr-1",
            "grade_subject_offering_id": "offering-1",
        },
    )
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["parse_degraded"] is False
    assert len(data["topics"]) == 2


@pytest.mark.asyncio
async def test_draft_autosave_and_resume(client: AsyncClient) -> None:
    empty = await client.get("/api/v1/teachers/me/lecture-draft")
    assert empty.status_code == 200
    assert empty.json()["data"]["id"] is None
    assert empty.json()["data"]["step"] == 1

    saved = await client.put(
        "/api/v1/teachers/me/lecture-draft",
        json={
            "step": 2,
            "data": {
                "grade_subject_offering_id": "offering-1",
                "topic": "Third law",
                "curriculum_id": "curr-1",
            },
        },
    )
    assert saved.status_code == 200
    body = saved.json()["data"]
    assert body["step"] == 2
    assert body["id"] is not None

    resumed = await client.get("/api/v1/teachers/me/lecture-draft")
    assert resumed.status_code == 200
    assert resumed.json()["data"]["step"] == 2
    assert resumed.json()["data"]["data"]["topic"] == "Third law"


@pytest.mark.asyncio
async def test_draft_rejects_unassigned_offering(client: AsyncClient) -> None:
    res = await client.put(
        "/api/v1/teachers/me/lecture-draft",
        json={"step": 1, "data": {"grade_subject_offering_id": "other-offering"}},
    )
    assert res.status_code == 404
