"""API contract tests for Offering endpoints — T-045/T-046."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.v1.router import router as v1_router
from app.core.dependencies import get_current_user, get_db
from app.core.exceptions import setup_exception_handlers
from app.features.grades.models import Grade, GradeStatus
from app.features.offerings.models import GradeSubjectOffering, OfferingStatus
from app.features.subjects.models import Subject, SubjectStatus
from app.features.users.models import User, UserAccountStatus, UserRole


class _FakeOfferingRepo:
    store: dict[str, GradeSubjectOffering] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def list_by_grade(
        self, grade_id: str, include_archived: bool = False
    ) -> list[GradeSubjectOffering]:
        rows = [o for o in self.store.values() if o.grade_id == grade_id and o.deleted_at is None]
        if not include_archived:
            rows = [o for o in rows if o.status == OfferingStatus.ACTIVE]
        return rows

    async def get_by_id(self, id: str) -> GradeSubjectOffering | None:
        return self.store.get(id)

    async def get_by_grade_subject(
        self, grade_id: str, subject_id: str
    ) -> GradeSubjectOffering | None:
        return next(
            (
                o
                for o in self.store.values()
                if o.grade_id == grade_id and o.subject_id == subject_id and o.deleted_at is None
            ),
            None,
        )

    async def count_active_by_subject(self, subject_id: str) -> int:
        return sum(
            1
            for o in self.store.values()
            if o.subject_id == subject_id
            and o.status == OfferingStatus.ACTIVE
            and o.deleted_at is None
        )

    async def count_active_assignments_for_teacher(self, teacher_id: str) -> int:
        return sum(
            1
            for o in self.store.values()
            if o.assigned_teacher_id == teacher_id
            and o.status == OfferingStatus.ACTIVE
            and o.deleted_at is None
        )

    async def create(self, offering: GradeSubjectOffering) -> GradeSubjectOffering:
        now = datetime.now(timezone.utc)
        offering.created_at = now
        offering.updated_at = now
        self.store[offering.id] = offering
        return offering

    async def update(self, offering: GradeSubjectOffering) -> GradeSubjectOffering:
        offering.updated_at = datetime.now(timezone.utc)
        self.store[offering.id] = offering
        return offering

    async def archive_all_for_grade(self, grade_id: str) -> None:
        for o in self.store.values():
            if o.grade_id == grade_id:
                o.status = OfferingStatus.ARCHIVED


class _FakeSubjectRepo:
    store: dict[str, Subject] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def get_by_id(self, id: str) -> Subject | None:
        return self.store.get(id)

    async def list_by_school(self, school_id: str, include_archived: bool = False) -> list[Subject]:
        return list(self.store.values())

    async def get_active_by_name(self, school_id: str, name: str) -> Subject | None:
        return None

    async def create(self, subject: Subject) -> Subject:
        self.store[subject.id] = subject
        return subject

    async def update(self, subject: Subject) -> Subject:
        self.store[subject.id] = subject
        return subject

    async def soft_delete(self, subject: Subject) -> None:
        pass


class _FakeGradeRepo:
    store: dict[str, Grade] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def list_by_school_session(
        self, school_id: str, academic_session: str, include_archived: bool = False
    ) -> list[Grade]:
        return list(self.store.values())

    async def get_by_id(self, id: str) -> Grade | None:
        return self.store.get(id)

    async def get_by_name_session(
        self, school_id: str, name: str, academic_session: str
    ) -> Grade | None:
        return None

    async def create(self, grade: Grade) -> Grade:
        now = datetime.now(timezone.utc)
        grade.created_at = now
        grade.updated_at = now
        self.store[grade.id] = grade
        return grade

    async def update(self, grade: Grade) -> Grade:
        self.store[grade.id] = grade
        return grade


class _FakeSessionRepo:
    def __init__(self, session: Any) -> None:
        pass

    async def get_school_active_label(self, school_id: str) -> str | None:
        return "2025-2026"

    async def get_active(self, school_id: str) -> Any:
        return None


class _FakeSectionRepo:
    def __init__(self, session: Any) -> None:
        pass

    async def archive_all_for_grade(self, grade_id: str) -> None:
        pass

    async def create_default_internal(self, grade_id: str) -> Any:
        return None


class _FakeUserRepo:
    users: dict[str, User] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def get_by_id(self, user_id: str) -> User | None:
        return self.users.get(user_id)

    async def get_by_authentik_id(self, authentik_id: str) -> User | None:
        # In these unit tests we key the fake users by the same value
        # that comes in `claims.sub`.
        return self.users.get(authentik_id)

    async def list_by_school_and_role(self, school_id: str, role: UserRole) -> list[User]:
        return [u for u in self.users.values() if u.school_id == school_id and u.role == role]


def _seed() -> None:
    now = datetime.now(timezone.utc)
    _FakeOfferingRepo.store = {}
    _FakeGradeRepo.store = {
        "grade-9": Grade(
            id="grade-9",
            school_id="school-1",
            name="Grade 9",
            academic_session="2025-2026",
            level_ordinal=9,
            status=GradeStatus.ACTIVE,
        )
    }
    for g in _FakeGradeRepo.store.values():
        g.created_at = now
        g.updated_at = now

    _FakeSubjectRepo.store = {
        "sub-physics": Subject(
            id="sub-physics",
            school_id="school-1",
            name="Physics",
            language="en",
            status=SubjectStatus.ACTIVE,
        )
    }
    for s in _FakeSubjectRepo.store.values():
        s.created_at = now
        s.updated_at = now

    teacher = User(
        id="teacher-1",
        authentik_id="teacher-1",
        email="t@test.com",
        display_name="Teacher T",
        role=UserRole.TEACHER,
        status=UserAccountStatus.ACTIVE,
        school_id="school-1",
        teacher_capacity=5,
    )
    teacher.created_at = now
    teacher.updated_at = now

    coordinator = User(
        id="coord-internal-id",
        authentik_id="coord-1",
        email="c@test.com",
        display_name="Coordinator",
        role=UserRole.COORDINATOR,
        status=UserAccountStatus.ACTIVE,
        school_id="school-1",
        scoped_ids="Grade 9,Grade 10",
    )
    coordinator.created_at = now
    coordinator.updated_at = now

    admin = User(
        id="admin-1",
        authentik_id="admin-1",
        email="admin@test.com",
        display_name="School Admin",
        role=UserRole.SCHOOL_ADMIN,
        status=UserAccountStatus.ACTIVE,
        school_id="school-1",
    )
    admin.created_at = now
    admin.updated_at = now

    _FakeUserRepo.users = {
        "coord-1": coordinator,
        "teacher-1": teacher,
        "admin-1": admin,
    }


@pytest.fixture(autouse=True)
def _patch_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    _seed()
    monkeypatch.setattr("app.features.offerings.service.OfferingRepository", _FakeOfferingRepo)
    monkeypatch.setattr("app.features.offerings.service.SubjectRepository", _FakeSubjectRepo)
    monkeypatch.setattr("app.features.offerings.service.UserRepository", _FakeUserRepo)
    monkeypatch.setattr("app.features.grades.service.GradeRepository", _FakeGradeRepo)
    monkeypatch.setattr("app.features.grades.service.AcademicSessionRepository", _FakeSessionRepo)
    monkeypatch.setattr("app.features.grades.service.UserRepository", _FakeUserRepo)
    monkeypatch.setattr("app.features.grades.service.SectionRepository", _FakeSectionRepo)
    monkeypatch.setattr("app.features.grades.service.OfferingRepository", _FakeOfferingRepo)
    monkeypatch.setattr("app.features.subjects.service.SubjectRepository", _FakeSubjectRepo)
    monkeypatch.setattr("app.features.subjects.service.OfferingRepository", _FakeOfferingRepo)
    monkeypatch.setattr("app.features.subjects.service.audit", AsyncMock())
    monkeypatch.setattr("app.features.offerings.service.audit", AsyncMock())
    monkeypatch.setattr("app.features.offerings.service.notify_account_event", AsyncMock())
    monkeypatch.setattr("app.features.offerings.service.publish_structure_mutation", AsyncMock())


def _build_client(user_id: str = "coord-1", role: str = "coordinator") -> AsyncClient:
    app = FastAPI()
    app.include_router(v1_router, prefix="/api/v1")
    setup_exception_handlers(app)

    async def _fake_db() -> AsyncGenerator[Any, None]:
        yield AsyncMock()

    def _claims() -> dict[str, object]:
        return {"sub": user_id, "role": role, "school_id": "school-1"}

    app.dependency_overrides[get_db] = _fake_db
    app.dependency_overrides[get_current_user] = _claims
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def test_create_offering() -> None:
    async with _build_client() as client:
        resp = await client.post(
            "/api/v1/grades/grade-9/offerings/",
            json={"subject_id": "sub-physics"},
        )
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["subject_id"] == "sub-physics"
    assert data["assigned_teacher_id"] is None


async def test_duplicate_offering_rejected() -> None:
    async with _build_client() as client:
        await client.post("/api/v1/grades/grade-9/offerings/", json={"subject_id": "sub-physics"})
        dup = await client.post(
            "/api/v1/grades/grade-9/offerings/", json={"subject_id": "sub-physics"}
        )
    assert dup.status_code == 409


async def test_archive_subject_blocked_with_active_offering() -> None:
    async with _build_client() as client:
        await client.post("/api/v1/grades/grade-9/offerings/", json={"subject_id": "sub-physics"})
        blocked = await client.post("/api/v1/subjects/sub-physics/archive")
    assert blocked.status_code == 412


async def test_assign_teacher_and_capacity() -> None:
    async with _build_client() as client:
        created = await client.post(
            "/api/v1/grades/grade-9/offerings/", json={"subject_id": "sub-physics"}
        )
        offering = created.json()["data"]
        etag = offering["updated_at"]
        assigned = await client.post(
            f"/api/v1/grades/grade-9/offerings/{offering['id']}/assign",
            json={"teacher_id": "teacher-1"},
            headers={"If-Match": etag},
        )
    assert assigned.status_code == 200
    assert assigned.json()["data"]["assigned_teacher_id"] == "teacher-1"


async def test_capacity_precondition_failed() -> None:
    async with _build_client() as client:
        offering_ids = []
        for i in range(6):
            sub_id = f"sub-{i}"
            sub = Subject(
                id=sub_id,
                school_id="school-1",
                name=f"Subject {i}",
                language="en",
                status=SubjectStatus.ACTIVE,
            )
            now = datetime.now(timezone.utc)
            sub.created_at = now
            sub.updated_at = now
            _FakeSubjectRepo.store[sub_id] = sub
            resp = await client.post(
                "/api/v1/grades/grade-9/offerings/", json={"subject_id": sub_id}
            )
            offering_ids.append(resp.json()["data"]["id"])

        for oid in offering_ids[:5]:
            off = _FakeOfferingRepo.store[oid]
            await client.post(
                f"/api/v1/grades/grade-9/offerings/{oid}/assign",
                json={"teacher_id": "teacher-1"},
                headers={"If-Match": off.updated_at.isoformat()},
            )

        sixth = _FakeOfferingRepo.store[offering_ids[5]]
        blocked = await client.post(
            f"/api/v1/grades/grade-9/offerings/{offering_ids[5]}/assign",
            json={"teacher_id": "teacher-1"},
            headers={"If-Match": sixth.updated_at.isoformat()},
        )
    assert blocked.status_code == 412
    assert "Teacher T" in blocked.json()["error"]["message"]


async def test_school_admin_override_succeeds() -> None:
    async with _build_client() as client:
        offering_ids = []
        for i in range(6):
            sub_id = f"sub-o-{i}"
            sub = Subject(
                id=sub_id,
                school_id="school-1",
                name=f"Override Subject {i}",
                language="en",
                status=SubjectStatus.ACTIVE,
            )
            now = datetime.now(timezone.utc)
            sub.created_at = now
            sub.updated_at = now
            _FakeSubjectRepo.store[sub_id] = sub
            resp = await client.post(
                "/api/v1/grades/grade-9/offerings/", json={"subject_id": sub_id}
            )
            offering_ids.append(resp.json()["data"]["id"])

        for oid in offering_ids[:5]:
            off = _FakeOfferingRepo.store[oid]
            await client.post(
                f"/api/v1/grades/grade-9/offerings/{oid}/assign",
                json={"teacher_id": "teacher-1"},
                headers={"If-Match": off.updated_at.isoformat()},
            )

        sixth = _FakeOfferingRepo.store[offering_ids[5]]
    async with _build_client(user_id="admin-1", role="school_admin") as admin_client:
        ok = await admin_client.post(
            f"/api/v1/grades/grade-9/offerings/{offering_ids[5]}/assign",
            json={"teacher_id": "teacher-1", "override": True},
            headers={"If-Match": sixth.updated_at.isoformat()},
        )
    assert ok.status_code == 200


async def test_if_match_stale_returns_412() -> None:
    async with _build_client() as client:
        created = await client.post(
            "/api/v1/grades/grade-9/offerings/", json={"subject_id": "sub-physics"}
        )
        offering_id = created.json()["data"]["id"]
        stale = await client.post(
            f"/api/v1/grades/grade-9/offerings/{offering_id}/assign",
            json={"teacher_id": "teacher-1"},
            headers={"If-Match": "stale-timestamp"},
        )
    assert stale.status_code == 412
