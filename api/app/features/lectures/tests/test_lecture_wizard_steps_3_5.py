"""T-115 — wizard steps 3–5 API tests (references, estimate, generate)."""

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
from app.features.lectures.models import LectureStatus, SchoolLecture, SchoolLectureDraft
from app.features.lectures.schemas import TeachingMode
from app.features.lectures.service import estimate_generation_seconds
from app.features.library.school_models import (
    LibraryContentType,
    LibraryIngestionStatus,
    LibraryVisibility,
    SchoolLibraryItem,
)
from app.features.offerings.models import GradeSubjectOffering, OfferingStatus
from app.features.subjects.models import Subject, SubjectStatus
from app.features.teacher_onboarding.models import TeacherProfile
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
    topic_tree_jsonb={"chapters": [{"title": "A"}], "parse_degraded": False},
    created_by="teacher-1",
    visibility=LibraryVisibility.SCHOOL_PUBLIC,
)

REF_SAME = SchoolLibraryItem(
    id="ref-9",
    school_id="school-1",
    title="Grade 9 Ref",
    content_type=LibraryContentType.REFERENCE,
    language="en",
    subject_id="subj-1",
    grade_level_ordinal=9,
    storage_key="k2",
    sha256="b" * 64,
    ingestion_status=LibraryIngestionStatus.AVAILABLE,
    topic_tree_jsonb=None,
    created_by="teacher-1",
    visibility=LibraryVisibility.SCHOOL_PUBLIC,
)

REF_LOWER = SchoolLibraryItem(
    id="ref-8",
    school_id="school-1",
    title="Grade 8 Ref",
    content_type=LibraryContentType.REFERENCE,
    language="en",
    subject_id="subj-1",
    grade_level_ordinal=8,
    storage_key="k3",
    sha256="c" * 64,
    ingestion_status=LibraryIngestionStatus.AVAILABLE,
    topic_tree_jsonb=None,
    created_by="teacher-1",
    visibility=LibraryVisibility.SCHOOL_PUBLIC,
)

REF_HIGHER = SchoolLibraryItem(
    id="ref-10",
    school_id="school-1",
    title="Grade 10 Ref",
    content_type=LibraryContentType.REFERENCE,
    language="en",
    subject_id="subj-1",
    grade_level_ordinal=10,
    storage_key="k4",
    sha256="d" * 64,
    ingestion_status=LibraryIngestionStatus.AVAILABLE,
    topic_tree_jsonb=None,
    created_by="teacher-1",
    visibility=LibraryVisibility.SCHOOL_PUBLIC,
)

PROFILE = TeacherProfile(
    user_id="teacher-1",
    name="Teacher One",
    language_preference="en",
    region_province="Punjab",
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
        return [o for o in self.store.values() if o.assigned_teacher_id == teacher_id]

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
        content_type = kwargs.get("content_type")
        rows = [
            i
            for i in self.items.values()
            if content_type is None or i.content_type.value == content_type
        ]
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
        draft.created_at = datetime.now(timezone.utc)
        draft.updated_at = draft.created_at
        self.store[draft.id] = draft
        return draft

    async def update(self, draft: SchoolLectureDraft) -> SchoolLectureDraft:
        draft.updated_at = datetime.now(timezone.utc)
        self.store[draft.id] = draft
        return draft

    async def soft_delete(self, draft: SchoolLectureDraft) -> None:
        draft.deleted_at = datetime.now(timezone.utc)
        self.store[draft.id] = draft


class _FakeLectureRepo:
    store: dict[str, SchoolLecture] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def create(self, lecture: SchoolLecture) -> SchoolLecture:
        lecture.created_at = datetime.now(timezone.utc)
        lecture.updated_at = lecture.created_at
        self.store[lecture.id] = lecture
        return lecture


class _FakeProfileRepo:
    store: dict[str, TeacherProfile] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def get_by_user_id(self, user_id: str) -> TeacherProfile | None:
        return self.store.get(user_id)


@pytest.fixture(autouse=True)
def _patch(monkeypatch: pytest.MonkeyPatch) -> None:
    _FakeUserRepo.store = {TEACHER.id: TEACHER}
    _FakeOfferingRepo.store = {OFFERING.id: OFFERING}
    _FakeGradeRepo.store = {GRADE.id: GRADE}
    _FakeSubjectRepo.store = {SUBJECT.id: SUBJECT}
    _FakeLibraryRepo.items = {
        CURRICULUM.id: CURRICULUM,
        REF_SAME.id: REF_SAME,
        REF_LOWER.id: REF_LOWER,
        REF_HIGHER.id: REF_HIGHER,
    }
    _FakeDraftRepo.store = {}
    _FakeLectureRepo.store = {}
    _FakeProfileRepo.store = {PROFILE.user_id: PROFILE}
    monkeypatch.setattr("app.features.lectures.service.UserRepository", _FakeUserRepo)
    monkeypatch.setattr("app.features.lectures.service.OfferingRepository", _FakeOfferingRepo)
    monkeypatch.setattr("app.features.lectures.service.GradeRepository", _FakeGradeRepo)
    monkeypatch.setattr("app.features.lectures.service.SubjectRepository", _FakeSubjectRepo)
    monkeypatch.setattr("app.features.lectures.service.SchoolLibraryRepository", _FakeLibraryRepo)
    monkeypatch.setattr("app.features.lectures.service.LectureDraftRepository", _FakeDraftRepo)
    monkeypatch.setattr("app.features.lectures.service.LectureRepository", _FakeLectureRepo)
    monkeypatch.setattr("app.features.lectures.service.TeacherProfileRepository", _FakeProfileRepo)


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


def test_estimate_scales_with_refs_and_mode() -> None:
    auto = estimate_generation_seconds(reference_count=2, teaching_mode=TeachingMode.AUTO)
    manual = estimate_generation_seconds(reference_count=2, teaching_mode=TeachingMode.MANUAL)
    assert auto > manual
    assert auto >= 30


@pytest.mark.asyncio
async def test_references_default_hides_cross_grade(client: AsyncClient) -> None:
    res = await client.get(
        "/api/v1/teachers/me/lecture-wizard/references",
        params={"grade_subject_offering_id": "offering-1", "include_cross_grade": "false"},
    )
    assert res.status_code == 200
    ids = {r["id"] for r in res.json()["data"]}
    assert "ref-9" in ids
    assert "ref-8" not in ids
    assert "ref-10" not in ids


@pytest.mark.asyncio
async def test_references_cross_grade_toggle_reveals_lower_only(client: AsyncClient) -> None:
    res = await client.get(
        "/api/v1/teachers/me/lecture-wizard/references",
        params={"grade_subject_offering_id": "offering-1", "include_cross_grade": "true"},
    )
    assert res.status_code == 200
    ids = {r["id"] for r in res.json()["data"]}
    assert "ref-8" in ids
    assert "ref-9" in ids
    assert "ref-10" not in ids


@pytest.mark.asyncio
async def test_generate_transitions_to_generating(client: AsyncClient) -> None:
    res = await client.post(
        "/api/v1/teachers/me/lecture-wizard/generate",
        json={
            "grade_subject_offering_id": "offering-1",
            "topic": "Newton's Laws",
            "curriculum_id": "curr-1",
            "reference_book_ids": ["ref-9"],
            "teaching_mode": "auto",
            "include_cross_grade": False,
        },
    )
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["status"] == LectureStatus.GENERATING.value
    assert data["lecture_id"]
    assert data["estimated_seconds"] >= 30
    assert len(_FakeLectureRepo.store) == 1
    lecture = next(iter(_FakeLectureRepo.store.values()))
    assert lecture.status == LectureStatus.GENERATING
