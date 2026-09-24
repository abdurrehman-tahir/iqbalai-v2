"""T-151 / T-163 — lecture study session service tests."""

# mypy: disable-error-code="method-assign"

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import NotFoundError, PermissionDeniedError, ValidationError
from app.features.lectures import lecture_session as lecture_session_mod
from app.features.lectures.lecture_session import INACTIVITY_TIMEOUT, LectureSessionService
from app.features.lectures.models import (
    LectureSessionMode,
    LectureSessionStatus,
    LectureStatus,
    LectureTenantType,
    LectureType,
    SchoolLecture,
    SchoolLectureSession,
)
from app.features.lectures.schemas import (
    LectureSessionModeLiteral,
    LectureSessionModeUpdateRequest,
    LectureSessionOpenRequest,
)
from app.features.users.models import UserRole


def _now() -> datetime:
    return datetime(2026, 9, 21, 12, 0, 0, tzinfo=timezone.utc)


def _fake_user(**overrides: Any) -> MagicMock:
    user = MagicMock()
    user.id = overrides.get("id", "stu-1")
    user.role = overrides.get("role", UserRole.STUDENT)
    user.deleted_at = None
    user.school_id = overrides.get("school_id", "school-1")
    return user


def _fake_lecture(**overrides: Any) -> SchoolLecture:
    defaults: dict[str, Any] = {
        "id": "lec-1",
        "school_id": "school-1",
        "teacher_user_id": "teacher-1",
        "title": "Newton's Laws",
        "topic": "Newton's Laws",
        "lecture_type": LectureType.MAIN,
        "status": LectureStatus.PUBLISHED,
        "current_version_id": "ver-1",
        "grade_subject_offering_id": "gso-1",
        "tenant_type": LectureTenantType.SCHOOL,
    }
    defaults.update(overrides)
    return SchoolLecture(**defaults)


def _fake_row(**overrides: Any) -> SchoolLectureSession:
    now = _now()
    defaults: dict[str, Any] = {
        "id": "sess-1",
        "lecture_id": "lec-1",
        "student_user_id": "stu-1",
        "tenant_type": LectureTenantType.SCHOOL,
        "mode": LectureSessionMode.TEXT,
        "status": LectureSessionStatus.ACTIVE,
        "opened_at": now,
        "last_activity_at": now,
        "ended_at": None,
    }
    defaults.update(overrides)
    return SchoolLectureSession(**defaults)


@pytest.fixture
def svc(monkeypatch: pytest.MonkeyPatch) -> LectureSessionService:
    session = AsyncMock()
    service = LectureSessionService(session)
    service._users = MagicMock()
    service._users.get_by_id = AsyncMock(return_value=_fake_user())
    service._lectures = MagicMock()
    service._lectures.get_by_id = AsyncMock(return_value=_fake_lecture())
    service._sessions = MagicMock()
    service._lecture_svc = MagicMock()
    service._questions = MagicMock()
    service._questions.count_for_session = AsyncMock(return_value=0)
    service._questions.count_highlights_for_session = AsyncMock(return_value=0)
    monkeypatch.setattr(lecture_session_mod, "_utcnow", _now)
    monkeypatch.setattr(lecture_session_mod, "publish_session_opened", AsyncMock())
    monkeypatch.setattr(lecture_session_mod, "publish_session_closed", AsyncMock())
    return service


@pytest.mark.asyncio
async def test_open_session_creates_new_active_row(svc: LectureSessionService) -> None:
    student = _fake_user()
    lecture = _fake_lecture()
    svc._users.get_by_authentik_id = AsyncMock(return_value=student)
    svc._lectures.get_by_id = AsyncMock(return_value=lecture)
    svc._lecture_svc.student_can_access_lecture = AsyncMock(return_value=True)
    svc._sessions.end_stale_active = AsyncMock(return_value=[])

    created = _fake_row(id="sess-new")
    svc._sessions.create = AsyncMock(return_value=created)

    result = await svc.open_session({"sub": "auth-1"}, "lec-1", LectureSessionOpenRequest())

    assert result.id == "sess-new"
    assert result.status.value == "active"
    assert result.mode.value == "text"
    svc._sessions.create.assert_awaited_once()
    assert svc._sessions.create.await_args is not None
    created_arg = svc._sessions.create.await_args.args[0]
    assert isinstance(created_arg, SchoolLectureSession)
    assert created_arg.student_user_id == "stu-1"
    assert created_arg.lecture_id == "lec-1"
    lecture_session_mod.publish_session_opened.assert_awaited_once()  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_open_session_allows_concurrent_second_device(svc: LectureSessionService) -> None:
    """Acceptance #4 — two devices → two distinct active sessions (no unique active)."""
    student = _fake_user()
    lecture = _fake_lecture()
    svc._users.get_by_authentik_id = AsyncMock(return_value=student)
    svc._lectures.get_by_id = AsyncMock(return_value=lecture)
    svc._lecture_svc.student_can_access_lecture = AsyncMock(return_value=True)
    svc._sessions.end_stale_active = AsyncMock(return_value=[])
    svc._sessions.create = AsyncMock(side_effect=[_fake_row(id="sess-a"), _fake_row(id="sess-b")])

    a = await svc.open_session({"sub": "auth-1"}, "lec-1", LectureSessionOpenRequest())
    b = await svc.open_session({"sub": "auth-1"}, "lec-1", LectureSessionOpenRequest())
    assert a.id != b.id
    assert svc._sessions.create.await_count == 2


@pytest.mark.asyncio
async def test_open_rejects_unpublished_and_inaccessible(svc: LectureSessionService) -> None:
    student = _fake_user()
    svc._users.get_by_authentik_id = AsyncMock(return_value=student)
    svc._lectures.get_by_id = AsyncMock(return_value=_fake_lecture(status=LectureStatus.DRAFT))
    with pytest.raises(NotFoundError):
        await svc.open_session({"sub": "auth-1"}, "lec-1", LectureSessionOpenRequest())

    svc._lectures.get_by_id = AsyncMock(return_value=_fake_lecture())
    svc._lecture_svc.student_can_access_lecture = AsyncMock(return_value=False)
    with pytest.raises(PermissionDeniedError):
        await svc.open_session({"sub": "auth-1"}, "lec-1", LectureSessionOpenRequest())


@pytest.mark.asyncio
async def test_touch_ends_stale_then_rejects(svc: LectureSessionService) -> None:
    student = _fake_user()
    stale = _fake_row(last_activity_at=_now() - INACTIVITY_TIMEOUT - timedelta(minutes=1))
    ended = _fake_row(
        status=LectureSessionStatus.ENDED,
        ended_at=_now(),
        last_activity_at=stale.last_activity_at,
    )
    svc._users.get_by_authentik_id = AsyncMock(return_value=student)
    svc._sessions.get_by_id = AsyncMock(return_value=stale)
    svc._sessions.save = AsyncMock(return_value=ended)

    with pytest.raises(ValidationError, match="ended"):
        await svc.touch_activity({"sub": "auth-1"}, "sess-1")
    lecture_session_mod.publish_session_closed.assert_awaited_once()  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_reopen_after_timeout_is_new_session(svc: LectureSessionService) -> None:
    """Acceptance #3 — re-open after timeout creates a NEW session."""
    student = _fake_user()
    lecture = _fake_lecture()
    svc._users.get_by_authentik_id = AsyncMock(return_value=student)
    svc._lectures.get_by_id = AsyncMock(return_value=lecture)
    svc._lecture_svc.student_can_access_lecture = AsyncMock(return_value=True)
    ended_stale = _fake_row(
        id="sess-old",
        status=LectureSessionStatus.ENDED,
        ended_at=_now(),
    )
    svc._sessions.end_stale_active = AsyncMock(return_value=[ended_stale])
    svc._sessions.create = AsyncMock(return_value=_fake_row(id="sess-2"))

    result = await svc.open_session({"sub": "auth-1"}, "lec-1", LectureSessionOpenRequest())
    assert result.id == "sess-2"
    svc._sessions.end_stale_active.assert_awaited_once()
    assert lecture_session_mod.publish_session_closed.await_count == 1  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_set_mode_and_end(svc: LectureSessionService) -> None:
    student = _fake_user()
    row = _fake_row()
    svc._users.get_by_authentik_id = AsyncMock(return_value=student)
    svc._sessions.get_by_id = AsyncMock(return_value=row)

    voice_row = _fake_row(mode=LectureSessionMode.VOICE)
    ended_row = _fake_row(status=LectureSessionStatus.ENDED, ended_at=_now())
    svc._sessions.save = AsyncMock(side_effect=[voice_row, ended_row])
    svc._questions.count_for_session = AsyncMock(return_value=2)
    svc._questions.count_highlights_for_session = AsyncMock(return_value=1)

    updated = await svc.set_mode(
        {"sub": "auth-1"},
        "sess-1",
        LectureSessionModeUpdateRequest(mode=LectureSessionModeLiteral.VOICE),
    )
    assert updated.mode.value == "voice"

    ended = await svc.end_session({"sub": "auth-1"}, "sess-1")
    assert ended.status.value == "ended"
    lecture_session_mod.publish_session_closed.assert_awaited_once()  # type: ignore[attr-defined]
    closed_payload = lecture_session_mod.publish_session_closed.await_args.kwargs["payload"]  # type: ignore[attr-defined]
    assert closed_payload["question_count"] == 2
    assert closed_payload["highlight_count"] == 1
    assert closed_payload["end_reason"] == "explicit"
    assert closed_payload["school_id"] == "school-1"


@pytest.mark.asyncio
async def test_end_inactive_helper(monkeypatch: pytest.MonkeyPatch) -> None:
    session = AsyncMock()
    ended_row = _fake_row(status=LectureSessionStatus.ENDED, ended_at=_now())
    repo = MagicMock()
    repo.end_stale_active = AsyncMock(return_value=[ended_row])
    monkeypatch.setattr(
        "app.features.lectures.lecture_session.LectureSessionRepository",
        lambda _s: repo,
    )
    emit = AsyncMock()
    monkeypatch.setattr(
        "app.features.lectures.lecture_session.LectureSessionService._emit_session_closed",
        emit,
    )
    monkeypatch.setattr(lecture_session_mod, "_utcnow", _now)
    result = await lecture_session_mod.end_inactive_lecture_sessions(session)
    assert result["ended_count"] == 1
    emit.assert_awaited_once()
