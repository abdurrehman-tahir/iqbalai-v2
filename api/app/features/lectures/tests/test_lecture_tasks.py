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

from app.features.lectures.models import LectureStatus
from app.features.lectures.tasks import generate_lecture

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
