"""Cross-grade / cross-subject lecture linking API tests — T-122, #21."""

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
from app.features.lectures.models import LectureStatus, SchoolLecture, SchoolLectureLink
from app.features.offerings.models import GradeSubjectOffering, OfferingStatus
from app.features.subjects.models import Subject
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

GRADE_9 = Grade(
    id="grade-9",
    school_id="school-1",
    name="Grade 9",
    academic_session="2025-2026",
    level_ordinal=9,
    status=GradeStatus.ACTIVE,
)
GRADE_8 = Grade(
    id="grade-8",
    school_id="school-1",
    name="Grade 8",
    academic_session="2025-2026",
    level_ordinal=8,
    status=GradeStatus.ACTIVE,
)
GRADE_10 = Grade(
    id="grade-10",
    school_id="school-1",
    name="Grade 10",
    academic_session="2025-2026",
    level_ordinal=10,
    status=GradeStatus.ACTIVE,
)

PHYSICS = Subject(id="subj-physics", school_id="school-1", name="Physics")
CHEMISTRY = Subject(id="subj-chem", school_id="school-1", name="Chemistry")

# Source offering: teacher-1's Grade 9 Physics.
OFFERING_G9_PHYSICS = GradeSubjectOffering(
    id="off-g9-physics",
    school_id="school-1",
    grade_id="grade-9",
    subject_id="subj-physics",
    assigned_teacher_id="teacher-1",
    academic_session="2025-2026",
    status=OfferingStatus.ACTIVE,
)
# Same teacher, lower grade, different subject — cross-grade AND cross-subject target.
OFFERING_G8_CHEMISTRY = GradeSubjectOffering(
    id="off-g8-chem",
    school_id="school-1",
    grade_id="grade-8",
    subject_id="subj-chem",
    assigned_teacher_id="teacher-1",
    academic_session="2025-2026",
    status=OfferingStatus.ACTIVE,
)
# Same teacher, higher grade — must be blocked.
OFFERING_G10_PHYSICS = GradeSubjectOffering(
    id="off-g10-physics",
    school_id="school-1",
    grade_id="grade-10",
    subject_id="subj-physics",
    assigned_teacher_id="teacher-1",
    academic_session="2025-2026",
    status=OfferingStatus.ACTIVE,
)
# Owned by the other teacher — not eligible as a self-link target.
OFFERING_G8_PHYSICS_OTHER_TEACHER = GradeSubjectOffering(
    id="off-g8-physics-other",
    school_id="school-1",
    grade_id="grade-8",
    subject_id="subj-physics",
    assigned_teacher_id="teacher-2",
    academic_session="2025-2026",
    status=OfferingStatus.ACTIVE,
)

LECTURE = SchoolLecture(
    id="lec-1",
    school_id="school-1",
    grade_subject_offering_id="off-g9-physics",
    teacher_user_id="teacher-1",
    title="Newton's Laws",
    topic="Newton's Laws",
    status=LectureStatus.READY_FOR_EDIT,
    current_version_id="ver-1",
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


class _FakeOfferingRepo:
    store: dict[str, GradeSubjectOffering] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def get_by_id(self, id: str) -> GradeSubjectOffering | None:
        return self.store.get(id)


class _FakeGradeRepo:
    store: dict[str, Grade] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def get_by_id(self, grade_id: str) -> Grade | None:
        return self.store.get(grade_id)


class _FakeSubjectRepo:
    store: dict[str, Subject] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def get_by_id(self, subject_id: str) -> Subject | None:
        return self.store.get(subject_id)


class _FakeLectureLinkRepo:
    rows: list[SchoolLectureLink]

    def __init__(self, session: Any) -> None:
        pass

    async def list_by_lecture(self, lecture_id: str) -> list[SchoolLectureLink]:
        return [link for link in _FakeLectureLinkRepo.rows if link.lecture_id == lecture_id]

    async def get_existing(
        self, lecture_id: str, target_grade_subject_offering_id: str
    ) -> SchoolLectureLink | None:
        return next(
            (
                link
                for link in _FakeLectureLinkRepo.rows
                if link.lecture_id == lecture_id
                and link.target_grade_subject_offering_id == target_grade_subject_offering_id
            ),
            None,
        )

    async def create(self, link: SchoolLectureLink) -> SchoolLectureLink:
        # Mirrors AuditMixin's DB-set created_at, which a real commit/refresh would
        # populate — this fake never actually flushes through a session.
        link.created_at = datetime.now(timezone.utc)
        _FakeLectureLinkRepo.rows.append(link)
        return link


_AUDIT_CALLS: list[dict[str, Any]] = []


@pytest.fixture(autouse=True)
def _patch_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    _FakeUserRepo.store = {TEACHER.id: TEACHER, OTHER_TEACHER.id: OTHER_TEACHER}
    _FakeLectureRepo.store = {LECTURE.id: LECTURE}
    _FakeOfferingRepo.store = {
        OFFERING_G9_PHYSICS.id: OFFERING_G9_PHYSICS,
        OFFERING_G8_CHEMISTRY.id: OFFERING_G8_CHEMISTRY,
        OFFERING_G10_PHYSICS.id: OFFERING_G10_PHYSICS,
        OFFERING_G8_PHYSICS_OTHER_TEACHER.id: OFFERING_G8_PHYSICS_OTHER_TEACHER,
    }
    _FakeGradeRepo.store = {GRADE_9.id: GRADE_9, GRADE_8.id: GRADE_8, GRADE_10.id: GRADE_10}
    _FakeSubjectRepo.store = {PHYSICS.id: PHYSICS, CHEMISTRY.id: CHEMISTRY}
    _FakeLectureLinkRepo.rows = []
    monkeypatch.setattr("app.features.lectures.service.UserRepository", _FakeUserRepo)
    monkeypatch.setattr("app.features.lectures.service.LectureRepository", _FakeLectureRepo)
    monkeypatch.setattr("app.features.lectures.service.OfferingRepository", _FakeOfferingRepo)
    monkeypatch.setattr("app.features.lectures.service.GradeRepository", _FakeGradeRepo)
    monkeypatch.setattr("app.features.lectures.service.SubjectRepository", _FakeSubjectRepo)
    monkeypatch.setattr("app.features.lectures.service.LectureLinkRepository", _FakeLectureLinkRepo)

    _AUDIT_CALLS.clear()

    async def _spy_audit(**kwargs: Any) -> None:
        _AUDIT_CALLS.append(kwargs)

    monkeypatch.setattr("app.features.lectures.service.audit", _spy_audit)


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
async def test_links_to_lower_grade_offering_allowed() -> None:
    async with _make_client(_fake_user) as client:
        res = await client.post(
            "/api/v1/teachers/me/lectures/lec-1/links",
            json={"target_grade_subject_offering_id": "off-g8-chem"},
        )

    assert res.status_code == 200
    data = res.json()["data"]
    assert data["target_grade_subject_offering_id"] == "off-g8-chem"
    assert data["target_grade_name"] == "Grade 8"
    assert data["target_grade_level_ordinal"] == 8
    assert data["target_subject_name"] == "Chemistry"
    # T-126: linking a lecture is audit-logged (Acceptance #3).
    from app.features.audit.actions import LECTURE_LINKED

    assert any(c["action"] == LECTURE_LINKED for c in _AUDIT_CALLS)


@pytest.mark.asyncio
async def test_cross_subject_linking_within_allowed_grade_works() -> None:
    """Item 3: linking to a different subject at an allowed grade is not blocked."""
    async with _make_client(_fake_user) as client:
        res = await client.post(
            "/api/v1/teachers/me/lectures/lec-1/links",
            json={"target_grade_subject_offering_id": "off-g8-chem"},
        )

    assert res.status_code == 200
    assert res.json()["data"]["target_subject_id"] == "subj-chem"


@pytest.mark.asyncio
async def test_link_to_higher_grade_blocked_forbidden() -> None:
    """Item 2: reverse-direction link raises PermissionDeniedError -> 403 FORBIDDEN,
    reusing T-047's assert_cross_grade_access_by_ordinal guard directly."""
    async with _make_client(_fake_user) as client:
        res = await client.post(
            "/api/v1/teachers/me/lectures/lec-1/links",
            json={"target_grade_subject_offering_id": "off-g10-physics"},
        )

    assert res.status_code == 403


@pytest.mark.asyncio
async def test_link_to_offering_not_owned_by_teacher_not_found() -> None:
    async with _make_client(_fake_user) as client:
        res = await client.post(
            "/api/v1/teachers/me/lectures/lec-1/links",
            json={"target_grade_subject_offering_id": "off-g8-physics-other"},
        )

    assert res.status_code == 404


@pytest.mark.asyncio
async def test_duplicate_link_rejected() -> None:
    async with _make_client(_fake_user) as client:
        first = await client.post(
            "/api/v1/teachers/me/lectures/lec-1/links",
            json={"target_grade_subject_offering_id": "off-g8-chem"},
        )
        assert first.status_code == 200
        second = await client.post(
            "/api/v1/teachers/me/lectures/lec-1/links",
            json={"target_grade_subject_offering_id": "off-g8-chem"},
        )

    assert second.status_code == 422


@pytest.mark.asyncio
async def test_link_to_own_offering_rejected() -> None:
    async with _make_client(_fake_user) as client:
        res = await client.post(
            "/api/v1/teachers/me/lectures/lec-1/links",
            json={"target_grade_subject_offering_id": "off-g9-physics"},
        )

    assert res.status_code == 422


@pytest.mark.asyncio
async def test_non_owning_teacher_cannot_link_lecture() -> None:
    async with _make_client(_fake_other_user) as client:
        res = await client.post(
            "/api/v1/teachers/me/lectures/lec-1/links",
            json={"target_grade_subject_offering_id": "off-g8-chem"},
        )

    assert res.status_code == 404


@pytest.mark.asyncio
async def test_links_render_in_lecture_detail() -> None:
    """Item 5: links render in the lecture detail (list endpoint)."""
    async with _make_client(_fake_user) as client:
        create_res = await client.post(
            "/api/v1/teachers/me/lectures/lec-1/links",
            json={"target_grade_subject_offering_id": "off-g8-chem"},
        )
        assert create_res.status_code == 200

        list_res = await client.get("/api/v1/teachers/me/lectures/lec-1/links")

    assert list_res.status_code == 200
    data = list_res.json()["data"]
    assert len(data) == 1
    assert data[0]["target_grade_subject_offering_id"] == "off-g8-chem"


@pytest.mark.asyncio
async def test_empty_links_list_for_unlinked_lecture() -> None:
    async with _make_client(_fake_user) as client:
        res = await client.get("/api/v1/teachers/me/lectures/lec-1/links")

    assert res.status_code == 200
    assert res.json()["data"] == []
