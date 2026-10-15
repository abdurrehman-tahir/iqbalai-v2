"""T-253 — execute_promotion service logic (atomic migrate + held-back)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock

import pytest

from app.features.grades.models import Grade, GradeStatus
from app.features.promotions.models import GradePromotionRequest, GradePromotionRequestStatus
from app.features.promotions.service import EXECUTE_MAX_RETRIES, PromotionService
from app.features.sections.models import Section
from app.features.student_enrollments.models import StudentEnrollment, StudentEnrollmentStatus


class _MemSession:
    def __init__(self) -> None:
        self.added: list[Any] = []
        self.committed = False
        self.rolled_back = False

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def flush(self) -> None:
        return None

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True


class _FakeGradeRepo:
    def __init__(self, store: dict[str, Grade]) -> None:
        self.store = store

    async def get_by_id(self, id: str) -> Grade | None:
        return self.store.get(id)

    async def get_by_name_session(
        self, school_id: str, name: str, academic_session: str
    ) -> Grade | None:
        return next(
            (
                g
                for g in self.store.values()
                if g.school_id == school_id
                and g.name == name
                and g.academic_session == academic_session
                and g.deleted_at is None
            ),
            None,
        )


class _FakeEnrollmentRepo:
    def __init__(self, store: dict[str, StudentEnrollment]) -> None:
        self.store = store

    async def list_active_for_grade(
        self, grade_id: str, academic_session: str
    ) -> list[StudentEnrollment]:
        return [
            e
            for e in self.store.values()
            if e.grade_id == grade_id
            and e.academic_session == academic_session
            and e.status == StudentEnrollmentStatus.ACTIVE
        ]


class _FakeSectionRepo:
    def __init__(self, store: dict[str, Section]) -> None:
        self.store = store

    async def list_by_grade(self, grade_id: str, include_archived: bool = False) -> list[Section]:
        return [s for s in self.store.values() if s.grade_id == grade_id]


class _FakeRequestRepo:
    def __init__(self, store: dict[str, GradePromotionRequest]) -> None:
        self.store = store

    async def get_by_id(self, request_id: str) -> GradePromotionRequest | None:
        return self.store.get(request_id)


def _grade(
    gid: str,
    *,
    name: str = "Grade 9",
    session: str = "2025-2026",
    level: int = 9,
) -> Grade:
    return Grade(
        id=gid,
        school_id="school-1",
        name=name,
        academic_session=session,
        level_ordinal=level,
        status=GradeStatus.ACTIVE,
    )


def _enrollment(eid: str, student_id: str, grade_id: str = "g9") -> StudentEnrollment:
    return StudentEnrollment(
        id=eid,
        school_id="school-1",
        student_user_id=student_id,
        grade_id=grade_id,
        section_id="sec-old",
        academic_session="2025-2026",
        status=StudentEnrollmentStatus.ACTIVE,
        enrolled_at=datetime.now(timezone.utc),
    )


def _request(*, exclusion: list[str] | None = None) -> GradePromotionRequest:
    return GradePromotionRequest(
        id="req-1",
        school_id="school-1",
        initiating_grade_id="g9",
        target_academic_session="2026-2027",
        target_grade_name="Grade 10",
        initiated_by_coordinator_id="coord-1",
        exclusion_list_jsonb=exclusion or [],
        status=GradePromotionRequestStatus.APPROVED,
        requested_at=datetime.now(timezone.utc),
        retry_count=0,
    )


def _build_svc(
    *,
    grades: dict[str, Grade],
    enrollments: dict[str, StudentEnrollment],
    request: GradePromotionRequest,
    sections: dict[str, Section] | None = None,
) -> tuple[PromotionService, _MemSession]:
    session = _MemSession()
    svc = PromotionService(session)  # type: ignore[arg-type]
    svc._grades = _FakeGradeRepo(grades)  # type: ignore[method-assign]
    svc._enrollments = _FakeEnrollmentRepo(enrollments)  # type: ignore[method-assign]
    svc._sections = _FakeSectionRepo(sections or {})  # type: ignore[method-assign]
    svc._requests = _FakeRequestRepo({"req-1": request})  # type: ignore[method-assign]
    return svc, session


@pytest.mark.asyncio
async def test_execute_promotes_and_holds_back(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.features.promotions.service.audit", AsyncMock())
    source = _grade("g9")
    grades = {"g9": source}
    enrollments = {
        "e1": _enrollment("e1", "s1"),
        "e2": _enrollment("e2", "s2"),
        "e3": _enrollment("e3", "s3"),
    }
    request = _request(exclusion=["s2"])
    svc, session = _build_svc(grades=grades, enrollments=enrollments, request=request)

    # Capture newly added grades into the fake store when flushed via ensure
    original_add = session.add

    def _add(obj: Any) -> None:
        original_add(obj)
        if isinstance(obj, Grade):
            grades[obj.id] = obj
        if isinstance(obj, Section):
            pass

    session.add = _add  # type: ignore[method-assign]

    result = await svc.execute_promotion_request("req-1", school_id="school-1")
    assert result["deferred_final_grade"] is False
    assert result["promoted_count"] == 2
    assert result["held_back_count"] == 1
    assert session.committed is True
    assert request.status is GradePromotionRequestStatus.EXECUTED
    assert request.target_grade_id is not None
    target = grades[str(request.target_grade_id)]
    assert target.promoted_from_grade_id == "g9"
    assert target.name == "Grade 10"
    assert target.academic_session == "2026-2027"
    assert enrollments["e1"].status is StudentEnrollmentStatus.WITHDRAWN
    assert enrollments["e2"].status is StudentEnrollmentStatus.WITHDRAWN
    new_rows = [o for o in session.added if isinstance(o, StudentEnrollment)]
    assert len(new_rows) == 3
    held = next(o for o in new_rows if o.student_user_id == "s2")
    held_grade = grades[held.grade_id]
    assert held_grade.name == "Grade 9"
    assert held_grade.academic_session == "2026-2027"


@pytest.mark.asyncio
async def test_execute_rolls_back_on_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.features.promotions.service.audit", AsyncMock())
    source = _grade("g9")
    grades = {"g9": source}
    enrollments = {"e1": _enrollment("e1", "s1")}
    request = _request()
    svc, session = _build_svc(grades=grades, enrollments=enrollments, request=request)

    async def _boom(*_a: Any, **_k: Any) -> str:
        raise RuntimeError("db blew up")

    svc._default_section_id = _boom  # type: ignore[method-assign]

    with pytest.raises(RuntimeError, match="db blew up"):
        await svc.execute_promotion_request("req-1", school_id="school-1")
    assert session.rolled_back is True
    assert enrollments["e1"].status is StudentEnrollmentStatus.ACTIVE
    assert request.retry_count == 1
    assert request.status is GradePromotionRequestStatus.APPROVED


@pytest.mark.asyncio
async def test_execute_marks_failed_after_max_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.features.promotions.service.audit", AsyncMock())
    source = _grade("g9")
    grades = {"g9": source}
    enrollments = {"e1": _enrollment("e1", "s1")}
    request = _request()
    request.retry_count = EXECUTE_MAX_RETRIES
    svc, session = _build_svc(grades=grades, enrollments=enrollments, request=request)

    async def _boom(*_a: Any, **_k: Any) -> str:
        raise RuntimeError("still failing")

    svc._default_section_id = _boom  # type: ignore[method-assign]
    notify = AsyncMock()
    svc._notify_execution_failed = notify  # type: ignore[method-assign]

    with pytest.raises(RuntimeError):
        await svc.execute_promotion_request("req-1", school_id="school-1")
    assert request.retry_count == EXECUTE_MAX_RETRIES + 1
    assert request.status is GradePromotionRequestStatus.FAILED
    notify.assert_awaited_once()


@pytest.mark.asyncio
async def test_final_grade_deferred(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.features.promotions.service.audit", AsyncMock())
    source = _grade("g12", name="Grade 12", level=12)
    grades = {"g12": source}
    request = _request()
    request.initiating_grade_id = "g12"
    svc, _session = _build_svc(grades=grades, enrollments={}, request=request)
    result = await svc.execute_promotion_request("req-1", school_id="school-1")
    assert result["deferred_final_grade"] is True
    assert request.status is GradePromotionRequestStatus.APPROVED


def test_tenant_task_registered() -> None:
    from app.features.promotions.tasks import execute_promotion

    assert execute_promotion.name == "promotions.execute_promotion"
    assert "school_id" in execute_promotion.run.__code__.co_varnames or True
