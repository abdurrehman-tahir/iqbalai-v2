"""generate_lecture Celery task failure-path tests — T-117.

T-116 already covers the happy path via `run_lecture_generation` directly;
these cover the task wrapper's timeout/exception handling, which T-117 wires
to also notify the WS stream buffer (`mark_failed`) so a connected teacher
sees a clean failure instead of a silent stall.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from celery.exceptions import SoftTimeLimitExceeded

from app.features.lectures.models import LectureStatus, LectureType, SchoolLecture
from app.features.lectures.tasks import (
    _handle_generation_failure,
    _handle_generation_timeout,
    generate_lecture,
)

_KWARGS: dict[str, Any] = {
    "lecture_id": "lec-1",
    "school_id": "school-1",
    "topic": "Forces",
    "curriculum_id": "curr-1",
    "reference_book_ids": [],
    "teaching_mode": "auto",
    "teacher_user_id": "teacher-1",
}


def test_soft_timeout_marks_timed_out_and_notifies_stream() -> None:
    task = generate_lecture

    with (
        patch("app.features.lectures.tasks.run_db") as mock_run_db,
        patch("app.features.lectures.tasks.mark_failed", new_callable=AsyncMock) as mock_mark,
    ):
        # First run_db call is the `_run_generation` lambda (raises); second is
        # the except block's `_mark_status` call (succeeds).
        mock_run_db.side_effect = [SoftTimeLimitExceeded(), None]
        result = task.run(**_KWARGS)

    assert result == {"lecture_id": "lec-1", "status": "timed_out"}
    assert mock_run_db.call_count == 2
    mock_mark.assert_awaited_once_with("lec-1", reason="timed_out")


def test_generic_failure_marks_failed_and_notifies_stream() -> None:
    task = generate_lecture

    with (
        patch("app.features.lectures.tasks.run_db") as mock_run_db,
        patch("app.features.lectures.tasks.mark_failed", new_callable=AsyncMock) as mock_mark,
    ):
        mock_run_db.side_effect = [RuntimeError("LLM provider down"), None]
        with pytest.raises(RuntimeError, match="LLM provider down"):
            task.run(**_KWARGS)

    assert mock_run_db.call_count == 2
    mock_mark.assert_awaited_once_with("lec-1", reason="LLM provider down")


def test_success_path_does_not_call_mark_failed() -> None:
    task = generate_lecture

    with (
        patch("app.features.lectures.tasks.run_db", return_value="ver-1") as mock_run_db,
        patch("app.features.lectures.tasks.mark_failed", new_callable=AsyncMock) as mock_mark,
    ):
        result = task.run(**_KWARGS)

    assert result == {"lecture_id": "lec-1", "version_id": "ver-1", "status": "generated_v1"}
    mock_run_db.assert_called_once()
    mock_mark.assert_not_awaited()


def test_status_enum_has_timed_out_and_failed() -> None:
    assert LectureStatus.TIMED_OUT.value == "timed_out"
    assert LectureStatus.FAILED.value == "failed"


# --- T-126: audit + notify + NATS on the failure/timeout status transitions --


def _lecture() -> SchoolLecture:
    return SchoolLecture(
        id="lec-1",
        school_id="school-1",
        teacher_user_id="teacher-1",
        title="Forces",
        topic="Forces",
        lecture_type=LectureType.MAIN,
        status=LectureStatus.GENERATING,
    )


@pytest.mark.asyncio
async def test_handle_generation_timeout_audits_notifies_and_publishes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lecture = _lecture()
    session = AsyncMock()
    session.get = AsyncMock(return_value=lecture)

    audit_calls: list[dict[str, Any]] = []
    notify_calls: list[dict[str, Any]] = []
    published: list[dict[str, Any]] = []

    async def _spy_audit(**kwargs: Any) -> None:
        audit_calls.append(kwargs)

    async def _spy_notify(session: Any, *, lecture: Any) -> None:
        notify_calls.append({"lecture_id": lecture.id})

    async def _spy_publish(*, event_type: str, payload: dict[str, Any]) -> None:
        published.append({"event_type": event_type, "payload": payload})

    monkeypatch.setattr("app.features.lectures.tasks.audit", _spy_audit)
    monkeypatch.setattr("app.features.lectures.tasks.notify_generation_timeout", _spy_notify)
    monkeypatch.setattr("app.features.lectures.tasks.publish_lecture_event", _spy_publish)

    await _handle_generation_timeout(session, "lec-1", "school-1")

    assert lecture.status == LectureStatus.TIMED_OUT
    assert audit_calls[0]["action"] == "lecture.generation_timed_out"
    assert audit_calls[0]["target_id"] == "lec-1"
    assert notify_calls == [{"lecture_id": "lec-1"}]
    assert published[0]["event_type"] == "lecture.generation_timed_out"


@pytest.mark.asyncio
async def test_handle_generation_failure_audits_notifies_and_publishes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lecture = _lecture()
    session = AsyncMock()
    session.get = AsyncMock(return_value=lecture)

    audit_calls: list[dict[str, Any]] = []
    notify_calls: list[dict[str, Any]] = []
    published: list[dict[str, Any]] = []

    async def _spy_audit(**kwargs: Any) -> None:
        audit_calls.append(kwargs)

    async def _spy_notify(session: Any, *, lecture: Any, error: str) -> None:
        notify_calls.append({"lecture_id": lecture.id, "error": error})

    async def _spy_publish(*, event_type: str, payload: dict[str, Any]) -> None:
        published.append({"event_type": event_type, "payload": payload})

    monkeypatch.setattr("app.features.lectures.tasks.audit", _spy_audit)
    monkeypatch.setattr("app.features.lectures.tasks.notify_generation_failed", _spy_notify)
    monkeypatch.setattr("app.features.lectures.tasks.publish_lecture_event", _spy_publish)

    await _handle_generation_failure(session, "lec-1", "school-1", "LLM provider down")

    assert lecture.status == LectureStatus.FAILED
    assert audit_calls[0]["action"] == "lecture.generation_failed"
    assert audit_calls[0]["metadata"]["error"] == "LLM provider down"
    assert notify_calls == [{"lecture_id": "lec-1", "error": "LLM provider down"}]
    assert published[0]["event_type"] == "lecture.generation_failed"
    assert published[0]["payload"]["error"] == "LLM provider down"


@pytest.mark.asyncio
async def test_handle_generation_failure_noop_for_unowned_lecture() -> None:
    """A lecture belonging to a different school must not be touched (defensive check).

    No mocks needed: the school_id mismatch returns before audit/notify/publish
    are ever reached, so a real (unmocked) ``audit``/``publish_lecture_event``
    call would prove the bug if this guard regressed.
    """
    lecture = _lecture()
    session = AsyncMock()
    session.get = AsyncMock(return_value=lecture)

    await _handle_generation_failure(session, "lec-1", "some-other-school", "boom")

    assert lecture.status == LectureStatus.GENERATING  # untouched
    session.commit.assert_not_awaited()
