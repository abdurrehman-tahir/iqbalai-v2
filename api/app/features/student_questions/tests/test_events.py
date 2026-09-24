"""T-163 — question / highlight NATS emission wiring."""

# mypy: disable-error-code="method-assign"

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.features.lectures.models import LectureSessionMode, LectureSessionStatus, LectureTenantType
from app.features.student_questions import service as service_mod
from app.features.student_questions.models import (
    QuestionClassification,
    SchoolStudentQuestion,
    StudentQuestionTenantType,
)
from app.features.student_questions.schemas import StudentQuestionCreateRequest
from app.features.student_questions.service import StudentQuestionService
from app.features.users.models import UserRole


def _now() -> datetime:
    return datetime(2026, 9, 21, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def svc(monkeypatch: pytest.MonkeyPatch) -> StudentQuestionService:
    session = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    service = StudentQuestionService(session)
    service._users = MagicMock()
    service._lectures = MagicMock()
    service._sessions = MagicMock()
    service._questions = MagicMock()
    service._conversations = MagicMock()
    service._paragraphs = MagicMock()
    service._lecture_svc = MagicMock()
    service._session_svc = MagicMock()
    monkeypatch.setattr(service_mod, "_utcnow", _now)
    monkeypatch.setattr(service_mod, "classify_question", MagicMock(return_value="knowledge_gap"))
    monkeypatch.setattr(
        service_mod,
        "to_model_enum",
        MagicMock(return_value=QuestionClassification.KNOWLEDGE_GAP),
    )
    monkeypatch.setattr(service_mod, "student_allows_teacher_share", AsyncMock(return_value=True))
    monkeypatch.setattr(service_mod, "enqueue_answer_generation", AsyncMock())
    monkeypatch.setattr(service_mod, "publish_student_question_asked", AsyncMock())
    monkeypatch.setattr(service_mod, "publish_student_highlight_created", AsyncMock())
    monkeypatch.setattr(
        service_mod,
        "question_to_read",
        MagicMock(return_value=MagicMock()),
    )
    return service


def _student() -> MagicMock:
    user = MagicMock()
    user.id = "stu-1"
    user.role = UserRole.STUDENT
    user.deleted_at = None
    user.authentik_id = "auth-1"
    user.school_id = "school-1"
    return user


def _lecture() -> MagicMock:
    lec = MagicMock()
    lec.id = "lec-1"
    lec.school_id = "school-1"
    return lec


def _session_row() -> MagicMock:
    row = MagicMock()
    row.id = "sess-1"
    row.lecture_id = "lec-1"
    row.student_user_id = "stu-1"
    row.status = LectureSessionStatus.ACTIVE
    row.tenant_type = LectureTenantType.SCHOOL
    row.mode = LectureSessionMode.TEXT
    row.last_activity_at = _now()
    return row


def _created_question(*, highlight_text: str | None) -> SchoolStudentQuestion:
    return SchoolStudentQuestion(
        id="q-1",
        student_user_id="stu-1",
        session_id="sess-1",
        lecture_id="lec-1",
        tenant_type=StudentQuestionTenantType.SCHOOL,
        highlight_text=highlight_text,
        question_text="Explain: F = ma",
        question_language="en",
        paragraph_id=None,
        source_chunk_id=None,
        classification=QuestionClassification.KNOWLEDGE_GAP,
        asked_at=_now(),
    )


@pytest.mark.asyncio
async def test_ask_emits_question_and_highlight(svc: StudentQuestionService) -> None:
    student = _student()
    lecture = _lecture()
    study = _session_row()
    created = _created_question(highlight_text="F = ma")

    svc._users.get_by_authentik_id = AsyncMock(return_value=student)
    svc._require_accessible_lecture = AsyncMock(return_value=lecture)  # type: ignore[method-assign]
    svc._require_active_owned_session = AsyncMock(return_value=study)  # type: ignore[method-assign]
    svc._resolve_source_chunk_id = AsyncMock(return_value=None)  # type: ignore[method-assign]
    svc._questions.create = AsyncMock(return_value=created)
    svc._conversations.create = AsyncMock(return_value=MagicMock())
    svc._conversations.list_for_question = AsyncMock(return_value=[])
    svc._sessions.save = AsyncMock(return_value=study)

    await svc.ask_question(
        {"sub": "auth-1"},
        lecture_id="lec-1",
        session_id="sess-1",
        payload=StudentQuestionCreateRequest(
            question_text="Explain: F = ma",
            highlight_text="F = ma",
            question_language="en",
        ),
    )

    service_mod.publish_student_question_asked.assert_awaited_once()  # type: ignore[attr-defined]
    service_mod.publish_student_highlight_created.assert_awaited_once()  # type: ignore[attr-defined]
    hl_payload = service_mod.publish_student_highlight_created.await_args.kwargs["payload"]  # type: ignore[attr-defined]
    assert hl_payload["highlight_text"] == "F = ma"
    assert hl_payload["tenant_type"] == "school"
    assert hl_payload["school_id"] == "school-1"


@pytest.mark.asyncio
async def test_ask_without_highlight_skips_highlight_event(svc: StudentQuestionService) -> None:
    student = _student()
    lecture = _lecture()
    study = _session_row()
    created = _created_question(highlight_text=None)

    svc._users.get_by_authentik_id = AsyncMock(return_value=student)
    svc._require_accessible_lecture = AsyncMock(return_value=lecture)  # type: ignore[method-assign]
    svc._require_active_owned_session = AsyncMock(return_value=study)  # type: ignore[method-assign]
    svc._resolve_source_chunk_id = AsyncMock(return_value=None)  # type: ignore[method-assign]
    svc._questions.create = AsyncMock(return_value=created)
    svc._conversations.create = AsyncMock(return_value=MagicMock())
    svc._conversations.list_for_question = AsyncMock(return_value=[])
    svc._sessions.save = AsyncMock(return_value=study)

    await svc.ask_question(
        {"sub": "auth-1"},
        lecture_id="lec-1",
        session_id="sess-1",
        payload=StudentQuestionCreateRequest(
            question_text="What is force?",
            question_language="en",
        ),
    )

    service_mod.publish_student_question_asked.assert_awaited_once()  # type: ignore[attr-defined]
    service_mod.publish_student_highlight_created.assert_not_awaited()  # type: ignore[attr-defined]
