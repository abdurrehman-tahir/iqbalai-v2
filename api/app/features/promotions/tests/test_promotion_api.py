"""API contract tests for promotion initiate — T-251."""

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
from app.features.promotions.models import GradePromotionRequest, GradePromotionRequestStatus
from app.features.student_enrollments.models import StudentEnrollment, StudentEnrollmentStatus
from app.features.users.models import User, UserAccountStatus, UserRole


class _FakeGradeRepo:
    store: dict[str, Grade] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def get_by_id(self, id: str) -> Grade | None:
        return self.store.get(id)


class _FakeEnrollmentRepo:
    store: dict[str, StudentEnrollment] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def list_active_for_grade(
        self, grade_id: str, academic_session: str
    ) -> list[StudentEnrollment]:
        return [
            e
            for e in self.store.values()
            if e.grade_id == grade_id
            and e.academic_session == academic_session
            and e.status == StudentEnrollmentStatus.ACTIVE
            and e.deleted_at is None
        ]


class _FakePromotionRepo:
    store: dict[str, GradePromotionRequest] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def get_pending_for_grade(self, grade_id: str) -> GradePromotionRequest | None:
        return next(
            (
                r
                for r in self.store.values()
                if r.initiating_grade_id == grade_id
                and r.status == GradePromotionRequestStatus.PENDING_APPROVAL
                and r.deleted_at is None
            ),
            None,
        )

    async def create(self, row: GradePromotionRequest) -> GradePromotionRequest:
        now = datetime.now(timezone.utc)
        row.created_at = now
        row.updated_at = now
        self.store[row.id] = row
        return row


class _FakeUserRepo:
    users: dict[str, User] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def get_by_authentik_id(self, authentik_id: str) -> User | None:
        return next(
            (u for u in self.users.values() if u.authentik_id == authentik_id),
            None,
        )

    async def get_by_id(self, user_id: str) -> User | None:
        return self.users.get(user_id)


def _coordinator(*, scope: str = "Grade 9", school_id: str = "school-1") -> User:
    return User(
        id="coord-1",
        authentik_id="coord-1",
        email="coord@test.com",
        display_name="Coord",
        role=UserRole.COORDINATOR,
        status=UserAccountStatus.ACTIVE,
        school_id=school_id,
        scoped_ids=scope,
    )


def _student(uid: str) -> User:
    return User(
        id=uid,
        authentik_id=uid,
        email=f"{uid}@test.com",
        display_name=uid,
        role=UserRole.STUDENT,
        status=UserAccountStatus.ACTIVE,
        school_id="school-1",
    )


def _grade(*, school_id: str = "school-1") -> Grade:
    return Grade(
        id="grade-9",
        school_id=school_id,
        name="Grade 9",
        academic_session="2025-2026",
        level_ordinal=9,
        status=GradeStatus.ACTIVE,
    )


def _enrollment(student_id: str) -> StudentEnrollment:
    return StudentEnrollment(
        id=f"enr-{student_id}",
        school_id="school-1",
        student_user_id=student_id,
        grade_id="grade-9",
        section_id="sec-a",
        academic_session="2025-2026",
        status=StudentEnrollmentStatus.ACTIVE,
        enrolled_at=datetime.now(timezone.utc),
    )


@pytest.fixture(autouse=True)
def _patch_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    _FakeGradeRepo.store = {"grade-9": _grade()}
    _FakeEnrollmentRepo.store = {
        "enr-s1": _enrollment("s1"),
        "enr-s2": _enrollment("s2"),
        "enr-s3": _enrollment("s3"),
    }
    _FakePromotionRepo.store = {}
    _FakeUserRepo.users = {
        "coord-1": _coordinator(),
        "s1": _student("s1"),
        "s2": _student("s2"),
        "s3": _student("s3"),
    }
    monkeypatch.setattr("app.features.promotions.service.GradeRepository", _FakeGradeRepo)
    monkeypatch.setattr(
        "app.features.promotions.service.StudentEnrollmentRepository", _FakeEnrollmentRepo
    )
    monkeypatch.setattr(
        "app.features.promotions.service.GradePromotionRequestRepository",
        _FakePromotionRepo,
    )
    monkeypatch.setattr("app.features.promotions.service.UserRepository", _FakeUserRepo)
    monkeypatch.setattr("app.features.promotions.service.audit", AsyncMock())


def _build_client(
    *,
    role: str = "coordinator",
    sub: str = "coord-1",
    school_id: str = "school-1",
) -> AsyncClient:
    app = FastAPI()
    app.include_router(v1_router, prefix="/api/v1")
    setup_exception_handlers(app)

    async def _override_user() -> dict[str, object]:
        return {"sub": sub, "role": role, "school_id": school_id}

    async def _override_db() -> AsyncGenerator[None, None]:
        yield None

    app.dependency_overrides[get_current_user] = _override_user
    app.dependency_overrides[get_db] = _override_db
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_create_promotion_with_exclusions() -> None:
    async with _build_client() as client:
        resp = await client.post(
            "/api/v1/grades/grade-9/promotion-requests/",
            json={
                "target_academic_session": "2026-2027",
                "target_grade_name": "Grade 10",
                "exclusion_list": ["s1", "s2"],
            },
        )
    assert resp.status_code == 201, resp.text
    body = resp.json()["data"]
    assert body["status"] == "pending_approval"
    assert body["exclusion_list_jsonb"] == ["s1", "s2"]
    assert body["initiating_grade_id"] == "grade-9"
    assert len(_FakePromotionRepo.store) == 1


@pytest.mark.asyncio
async def test_exclusion_not_enrolled_returns_422() -> None:
    async with _build_client() as client:
        resp = await client.post(
            "/api/v1/grades/grade-9/promotion-requests/",
            json={
                "target_academic_session": "2026-2027",
                "target_grade_name": "Grade 10",
                "exclusion_list": ["s1", "unknown"],
            },
        )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_out_of_scope_coordinator_returns_404() -> None:
    _FakeUserRepo.users["coord-1"] = _coordinator(scope="Grade 10")
    async with _build_client() as client:
        resp = await client.post(
            "/api/v1/grades/grade-9/promotion-requests/",
            json={
                "target_academic_session": "2026-2027",
                "target_grade_name": "Grade 10",
                "exclusion_list": [],
            },
        )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_cross_school_grade_returns_404() -> None:
    _FakeGradeRepo.store["grade-9"] = _grade(school_id="school-other")
    async with _build_client() as client:
        resp = await client.post(
            "/api/v1/grades/grade-9/promotion-requests/",
            json={
                "target_academic_session": "2026-2027",
                "target_grade_name": "Grade 10",
                "exclusion_list": [],
            },
        )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_second_pending_returns_412() -> None:
    async with _build_client() as client:
        first = await client.post(
            "/api/v1/grades/grade-9/promotion-requests/",
            json={
                "target_academic_session": "2026-2027",
                "target_grade_name": "Grade 10",
                "exclusion_list": [],
            },
        )
        assert first.status_code == 201
        second = await client.post(
            "/api/v1/grades/grade-9/promotion-requests/",
            json={
                "target_academic_session": "2026-2027",
                "target_grade_name": "Grade 10",
                "exclusion_list": [],
            },
        )
    assert second.status_code == 412
    assert second.json()["error"]["code"] == "PRECONDITION_FAILED"


@pytest.mark.asyncio
async def test_roster_lists_active_students() -> None:
    async with _build_client() as client:
        resp = await client.get("/api/v1/grades/grade-9/promotion-requests/roster")
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert {row["student_user_id"] for row in data} == {"s1", "s2", "s3"}
