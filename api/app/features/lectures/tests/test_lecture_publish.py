"""Lecture publish lifecycle — T-142."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.v1.router import router as v1_router
from app.core.dependencies import get_current_user, get_db
from app.core.exceptions import ValidationError, setup_exception_handlers
from app.features.audit.actions import LECTURE_OVERRIDE_PUBLISHED, LECTURE_PUBLISHED
from app.features.lectures.models import LectureStatus, SchoolLecture
from app.features.lectures.service import LectureWizardService
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
ADMIN = User(
    id="admin-1",
    authentik_id="auth-admin",
    email="admin@example.com",
    display_name="School Admin",
    role=UserRole.SCHOOL_ADMIN,
    status=UserAccountStatus.ACTIVE,
    school_id="school-1",
)


def _lecture(**overrides: object) -> SchoolLecture:
    row = SchoolLecture(
        id="lec-1",
        school_id="school-1",
        grade_subject_offering_id="off-1",
        teacher_user_id="teacher-1",
        title="Newton",
        topic="Newton's Laws",
        status=LectureStatus.READY_FOR_EDIT,
        current_version_id="ver-1",
    )
    for key, value in overrides.items():
        setattr(row, key, value)
    return row


class _FakeUsers:
    def __init__(self, user: User) -> None:
        self._user = user

    async def get_by_authentik_id(self, _aid: str) -> User:
        return self._user


class _FakeLectures:
    def __init__(self, lecture: SchoolLecture) -> None:
        self.lecture = lecture

    async def get_by_id(self, lecture_id: str) -> SchoolLecture | None:
        return self.lecture if lecture_id == self.lecture.id else None


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_teacher_publish_ready_for_edit(monkeypatch: pytest.MonkeyPatch) -> None:
    lecture = _lecture()
    svc = LectureWizardService(MagicMock())
    svc._users = _FakeUsers(TEACHER)  # type: ignore[method-assign]
    svc._lectures = _FakeLectures(lecture)  # type: ignore[method-assign]
    svc._session.commit = AsyncMock()
    svc._session.refresh = AsyncMock()

    audits: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []

    async def _audit(**kwargs: object) -> None:
        audits.append(dict(kwargs))

    async def _publish(**kwargs: object) -> None:
        events.append(dict(kwargs))

    async def _quiz_publish(_session: object, *, lecture_id: str) -> int:
        assert lecture_id == "lec-1"
        return 2

    async def _notify(_session: object, *, lecture: SchoolLecture) -> None:
        assert lecture.id == "lec-1"

    monkeypatch.setattr("app.features.lectures.service.audit", _audit)
    monkeypatch.setattr("app.features.lectures.service.publish_lecture_event", _publish)
    monkeypatch.setattr(
        "app.features.quizzes.publish.publish_pending_assignments_for_lecture",
        _quiz_publish,
    )
    monkeypatch.setattr(
        "app.features.lectures.lecture_notifications.notify_lecture_published",
        _notify,
    )

    result = await svc.publish_lecture({"sub": "auth-teacher"}, "lec-1")
    assert result.status == "published"
    assert result.override is False
    assert result.quizzes_published == 2
    assert lecture.status == LectureStatus.PUBLISHED
    assert audits[0]["action"] == LECTURE_PUBLISHED
    assert events[0]["event_type"] == "lecture.published"


@pytest.mark.anyio
async def test_admin_override_publish_is_elevated(monkeypatch: pytest.MonkeyPatch) -> None:
    lecture = _lecture(teacher_user_id="teacher-1")
    svc = LectureWizardService(MagicMock())
    svc._users = _FakeUsers(ADMIN)  # type: ignore[method-assign]
    svc._lectures = _FakeLectures(lecture)  # type: ignore[method-assign]
    svc._session.commit = AsyncMock()
    svc._session.refresh = AsyncMock()

    audits: list[dict[str, Any]] = []

    async def _audit(**kwargs: object) -> None:
        audits.append(dict(kwargs))

    monkeypatch.setattr("app.features.lectures.service.audit", _audit)
    monkeypatch.setattr(
        "app.features.lectures.service.publish_lecture_event", AsyncMock()
    )
    monkeypatch.setattr(
        "app.features.quizzes.publish.publish_pending_assignments_for_lecture",
        AsyncMock(return_value=0),
    )
    monkeypatch.setattr(
        "app.features.lectures.lecture_notifications.notify_lecture_published",
        AsyncMock(),
    )

    result = await svc.publish_lecture({"sub": "auth-admin"}, "lec-1")
    assert result.override is True
    assert audits[0]["action"] == LECTURE_OVERRIDE_PUBLISHED


@pytest.mark.anyio
async def test_publish_rejects_generating_status() -> None:
    lecture = _lecture(status=LectureStatus.GENERATING, current_version_id=None)
    svc = LectureWizardService(MagicMock())
    svc._users = _FakeUsers(TEACHER)  # type: ignore[method-assign]
    svc._lectures = _FakeLectures(lecture)  # type: ignore[method-assign]
    with pytest.raises(ValidationError):
        await svc.publish_lecture({"sub": "auth-teacher"}, "lec-1")


@pytest.mark.anyio
async def test_publish_api_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    app = FastAPI()
    setup_exception_handlers(app)
    app.include_router(v1_router, prefix="/api/v1")

    async def _db() -> AsyncGenerator[MagicMock, None]:
        yield MagicMock()

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_current_user] = lambda: {"sub": "auth-teacher", "role": "teacher"}

    async def _publish(self: object, claims: dict[str, object], lecture_id: str) -> Any:
        from app.features.lectures.schemas import LecturePublishRead

        return LecturePublishRead(
            id=lecture_id,
            status="published",
            current_version_id="ver-1",
            published_by_user_id="teacher-1",
            override=False,
            quizzes_published=0,
        )

    monkeypatch.setattr(LectureWizardService, "publish_lecture", _publish)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/v1/teachers/me/lectures/lec-1/publish")
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["status"] == "published"
    assert body["data"]["id"] == "lec-1"
