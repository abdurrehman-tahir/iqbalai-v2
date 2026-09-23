"""T-163 — NATS student lecture event emission (mock publish)."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.features.lectures import events as lecture_events
from app.features.lectures.events import (
    STUDENT_LECTURE_SESSION_CLOSED,
    STUDENT_LECTURE_SESSION_OPENED,
    publish_session_closed,
    publish_session_opened,
)
from app.features.student_questions import events as question_events
from app.features.student_questions.events import (
    STUDENT_HIGHLIGHT_CREATED,
    STUDENT_QUESTION_ASKED,
    publish_student_highlight_created,
    publish_student_question_asked,
)


@pytest.fixture
def publish_spy(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    spy = AsyncMock()
    monkeypatch.setattr(lecture_events, "publish", spy)
    monkeypatch.setattr(question_events, "publish", spy)
    return spy


@pytest.mark.asyncio
async def test_publish_session_opened_tenant_tagged(publish_spy: AsyncMock) -> None:
    payload = {
        "session_id": "sess-1",
        "lecture_id": "lec-1",
        "student_user_id": "stu-1",
        "school_id": "school-1",
        "tenant_type": "school",
        "mode": "text",
        "opened_at": "2026-09-21T12:00:00+00:00",
    }
    await publish_session_opened(payload=payload)

    publish_spy.assert_awaited_once()
    args, kwargs = publish_spy.await_args
    assert args[0] == STUDENT_LECTURE_SESSION_OPENED
    assert args[1] == STUDENT_LECTURE_SESSION_OPENED
    assert args[2] == payload
    assert kwargs["tenant_id"] == "school-1"
    assert kwargs["tenant_type"] == "school"
    assert kwargs["user_id"] == "stu-1"
    assert kwargs["session_id"] == "sess-1"


@pytest.mark.asyncio
async def test_publish_session_closed_includes_summary(publish_spy: AsyncMock) -> None:
    summary = {
        "session_id": "sess-1",
        "lecture_id": "lec-1",
        "student_user_id": "stu-1",
        "school_id": "school-1",
        "tenant_type": "school",
        "mode": "voice",
        "opened_at": "2026-09-21T12:00:00+00:00",
        "ended_at": "2026-09-21T12:20:00+00:00",
        "last_activity_at": "2026-09-21T12:20:00+00:00",
        "duration_seconds": 1200,
        "question_count": 3,
        "highlight_count": 2,
        "end_reason": "explicit",
    }
    await publish_session_closed(payload=summary)

    publish_spy.assert_awaited_once()
    args, kwargs = publish_spy.await_args
    assert args[0] == STUDENT_LECTURE_SESSION_CLOSED
    assert args[2]["question_count"] == 3
    assert args[2]["highlight_count"] == 2
    assert args[2]["end_reason"] == "explicit"
    assert kwargs["tenant_type"] == "school"
    assert kwargs["tenant_id"] == "school-1"


@pytest.mark.asyncio
async def test_publish_question_asked(publish_spy: AsyncMock) -> None:
    payload = {
        "question_id": "q-1",
        "student_user_id": "stu-1",
        "session_id": "sess-1",
        "lecture_id": "lec-1",
        "school_id": "school-1",
        "tenant_type": "school",
        "highlight_text": None,
    }
    await publish_student_question_asked(payload=payload)

    publish_spy.assert_awaited_once()
    args, kwargs = publish_spy.await_args
    assert args[0] == STUDENT_QUESTION_ASKED
    assert kwargs["tenant_id"] == "school-1"
    assert kwargs["session_id"] == "sess-1"


@pytest.mark.asyncio
async def test_publish_highlight_created(publish_spy: AsyncMock) -> None:
    payload = {
        "question_id": "q-1",
        "student_user_id": "stu-1",
        "session_id": "sess-1",
        "lecture_id": "lec-1",
        "school_id": "school-1",
        "tenant_type": "school",
        "highlight_text": "F = ma",
    }
    await publish_student_highlight_created(payload=payload)

    publish_spy.assert_awaited_once()
    args, kwargs = publish_spy.await_args
    assert args[0] == STUDENT_HIGHLIGHT_CREATED
    assert args[2]["highlight_text"] == "F = ma"
    assert kwargs["tenant_type"] == "school"


@pytest.mark.asyncio
async def test_publish_swallows_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    failing = AsyncMock(side_effect=RuntimeError("nats down"))
    monkeypatch.setattr(lecture_events, "publish", failing)
    monkeypatch.setattr(question_events, "publish", failing)

    await publish_session_opened(
        payload={
            "session_id": "s",
            "student_user_id": "u",
            "school_id": "sch",
            "tenant_type": "school",
        }
    )
    await publish_student_question_asked(
        payload={
            "student_user_id": "u",
            "school_id": "sch",
            "tenant_type": "school",
            "session_id": "s",
        }
    )
    # Must not raise — best-effort emit-only.
