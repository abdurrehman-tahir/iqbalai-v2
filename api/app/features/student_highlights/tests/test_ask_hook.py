"""T-185 — ask-question path persists the highlight in the same transaction."""

# mypy: disable-error-code="method-assign"

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.features.lectures.models import LectureSessionStatus, LectureTenantType
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
    return datetime(2026, 10, 3, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def setup(monkeypatch: pytest.MonkeyPatch) -> tuple[StudentQuestionService, MagicMock]:
    session = AsyncMock()
    service = StudentQuestionService(session)
    for attr in ("_users", "_sessions", "_questions", "_conversations", "_paragraphs"):
        setattr(service, attr, MagicMock())
    monkeypatch.setattr(service_mod, "_utcnow", _now)
    monkeypatch.setattr(service_mod, "classify_question", MagicMock(return_value="knowledge_gap"))
    monkeypatch.setattr(
        service_mod, "to_model_enum", MagicMock(return_value=QuestionClassification.KNOWLEDGE_GAP)
    )
    monkeypatch.setattr(service_mod, "student_allows_teacher_share", AsyncMock(return_value=True))
    monkeypatch.setattr(service_mod, "enqueue_answer_generation", AsyncMock())
    monkeypatch.setattr(service_mod, "publish_student_question_asked", AsyncMock())
    monkeypatch.setattr(service_mod, "publish_student_highlight_created", AsyncMock())
    monkeypatch.setattr(service_mod, "question_to_read", MagicMock(return_value=MagicMock()))

    highlight_svc = MagicMock()
    highlight_svc.persist_for_question = AsyncMock(return_value=None)
    monkeypatch.setattr(
        service_mod, "StudentHighlightService", MagicMock(return_value=highlight_svc)
    )

    student = MagicMock()
    student.id, student.role, student.deleted_at = "stu-1", UserRole.STUDENT, None
    lecture = MagicMock()
    lecture.id, lecture.school_id, lecture.current_version_id = "lec-1", "school-1", "ver-2"
    study = MagicMock()
    study.id, study.status, study.tenant_type = (
        "sess-1",
        LectureSessionStatus.ACTIVE,
        (LectureTenantType.SCHOOL),
    )
    created = SchoolStudentQuestion(
        id="q-1",
        student_user_id="stu-1",
        session_id="sess-1",
        lecture_id="lec-1",
        tenant_type=StudentQuestionTenantType.SCHOOL,
        highlight_text="mass",
        question_text="Explain",
        asked_at=_now(),
    )
    service._users.get_by_authentik_id = AsyncMock(return_value=student)
    service._require_accessible_lecture = AsyncMock(return_value=lecture)
    service._require_active_owned_session = AsyncMock(return_value=study)
    service._resolve_source_chunk_id = AsyncMock(return_value="chunk-9")
    service._questions.create = AsyncMock(return_value=created)
    service._conversations.create = AsyncMock()
    service._conversations.list_for_question = AsyncMock(return_value=[])
    service._sessions.save = AsyncMock()
    return service, highlight_svc


def _paragraph(version: str) -> Any:
    p = MagicMock()
    p.id, p.lecture_version_id, p.text = "p1", version, "Force equals mass times acceleration."
    return p


def _payload() -> StudentQuestionCreateRequest:
    return StudentQuestionCreateRequest(
        question_text="Explain",
        highlight_text="mass",
        highlight_offset=13,
        paragraph_id="p1",
    )


@pytest.mark.asyncio
async def test_ask_persists_highlight_with_current_version_paragraph(
    setup: tuple[StudentQuestionService, MagicMock],
) -> None:
    service, highlight_svc = setup
    para = _paragraph("ver-2")
    service._paragraphs.get_by_id = AsyncMock(return_value=para)

    await service.ask_question(
        {"sub": "a"}, lecture_id="lec-1", session_id="sess-1", payload=_payload()
    )

    kwargs = highlight_svc.persist_for_question.await_args.kwargs
    assert kwargs["paragraph"] is para
    assert kwargs["highlighted_text"] == "mass"
    assert kwargs["offset_hint"] == 13
    assert kwargs["question_id"] == "q-1"
    assert kwargs["tenant_type"] == "school"
    assert kwargs["source_chunk_id"] == "chunk-9"
    # Staged before the single commit of the ask transaction.
    session = service._session
    assert isinstance(session, AsyncMock)
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_ask_does_not_anchor_on_stale_version_paragraph(
    setup: tuple[StudentQuestionService, MagicMock],
) -> None:
    service, highlight_svc = setup
    service._paragraphs.get_by_id = AsyncMock(return_value=_paragraph("ver-1"))

    await service.ask_question(
        {"sub": "a"}, lecture_id="lec-1", session_id="sess-1", payload=_payload()
    )

    assert highlight_svc.persist_for_question.await_args.kwargs["paragraph"] is None


def test_highlight_offset_must_be_non_negative() -> None:
    with pytest.raises(ValueError):
        StudentQuestionCreateRequest(question_text="x", highlight_offset=-1)
