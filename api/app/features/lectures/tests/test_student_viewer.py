"""T-152 — student lecture viewer service tests."""

# mypy: disable-error-code="method-assign"

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import NotFoundError, PermissionDeniedError
from app.features.lectures.models import (
    LectureStatus,
    LectureTenantType,
    LectureType,
    SchoolLecture,
    SchoolLectureParagraph,
)
from app.features.lectures.schemas import (
    LectureSessionModeLiteral,
    LectureSessionOpenRequest,
    LectureSessionRead,
    LectureSessionStatusLiteral,
    SourceTier,
)
from app.features.lectures.student_viewer import StudentLectureViewerService
from app.features.users.models import UserRole


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
        "topic": "Forces",
        "lecture_type": LectureType.MAIN,
        "status": LectureStatus.PUBLISHED,
        "current_version_id": "ver-1",
        "grade_subject_offering_id": "gso-1",
        "tenant_type": LectureTenantType.SCHOOL,
    }
    defaults.update(overrides)
    return SchoolLecture(**defaults)


def _session_read() -> LectureSessionRead:
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    return LectureSessionRead(
        id="sess-1",
        lecture_id="lec-1",
        student_user_id="stu-1",
        tenant_type="school",
        mode=LectureSessionModeLiteral.TEXT,
        status=LectureSessionStatusLiteral.ACTIVE,
        opened_at=now,
        last_activity_at=now,
        ended_at=None,
    )


@pytest.fixture
def svc() -> StudentLectureViewerService:
    session = AsyncMock()
    service = StudentLectureViewerService(session)
    service._users = MagicMock()
    service._lectures = MagicMock()
    service._paragraphs = MagicMock()
    service._lecture_svc = MagicMock()
    service._sessions = MagicMock()
    return service


@pytest.mark.asyncio
async def test_open_viewer_returns_paragraphs_and_session(svc: StudentLectureViewerService) -> None:
    student = _fake_user()
    lecture = _fake_lecture()
    para = SchoolLectureParagraph(
        id="p1",
        lecture_version_id="ver-1",
        ordinal=0,
        text="Force equals mass times acceleration.",
        source_metadata_jsonb={"tier": "curriculum"},
    )
    svc._users.get_by_authentik_id = AsyncMock(return_value=student)
    svc._lectures.get_by_id = AsyncMock(return_value=lecture)
    svc._lecture_svc.student_can_access_lecture = AsyncMock(return_value=True)
    svc._sessions.open_session = AsyncMock(return_value=_session_read())
    svc._paragraphs.list_by_version = AsyncMock(return_value=[para])

    result = await svc.open_viewer(
        {"sub": "auth-1"}, "lec-1", mode_payload=LectureSessionOpenRequest()
    )

    assert result.lecture_id == "lec-1"
    assert result.current_version_id == "ver-1"
    assert result.session.id == "sess-1"
    assert len(result.paragraphs) == 1
    assert result.paragraphs[0].tier == SourceTier.CURRICULUM
    svc._sessions.open_session.assert_awaited_once()


@pytest.mark.asyncio
async def test_open_viewer_blocks_restricted(svc: StudentLectureViewerService) -> None:
    svc._users.get_by_authentik_id = AsyncMock(return_value=_fake_user())
    svc._lectures.get_by_id = AsyncMock(return_value=_fake_lecture())
    svc._lecture_svc.student_can_access_lecture = AsyncMock(return_value=False)
    with pytest.raises(PermissionDeniedError):
        await svc.open_viewer({"sub": "auth-1"}, "lec-1")


@pytest.mark.asyncio
async def test_open_viewer_requires_published(svc: StudentLectureViewerService) -> None:
    svc._users.get_by_authentik_id = AsyncMock(return_value=_fake_user())
    svc._lectures.get_by_id = AsyncMock(
        return_value=_fake_lecture(status=LectureStatus.READY_FOR_EDIT)
    )
    with pytest.raises(NotFoundError):
        await svc.open_viewer({"sub": "auth-1"}, "lec-1")
