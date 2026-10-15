"""T-196 — overnight aggregation beat + per-school bucketing tests."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from app.features.next_day_review.aggregation import (
    QUESTION_EVENT_TYPES,
    QuestionBucketKey,
    aggregate_school_day,
    bucket_key_from_event,
    karachi_day_bounds,
)
from app.features.next_day_review.tasks import (
    AGGREGATE_NIGHTLY_TASK,
    AGGREGATE_SCHOOL_TASK,
    aggregate_nightly,
)
from app.infrastructure.events.subjects import STUDENT_LECTURE_QUESTION_ASKED
from app.tasks.beat_schedule import BEAT_SCHEDULE


def test_beat_fires_at_2300_karachi() -> None:
    """Acceptance #1 — schedule is 23:00 Asia/Karachi (= 18:00 UTC)."""
    entry: Any = BEAT_SCHEDULE["review-aggregate-nightly"]
    assert entry["task"] == AGGREGATE_NIGHTLY_TASK
    schedule = entry["schedule"]
    assert schedule.hour == {18}
    assert schedule.minute == {0}


def test_question_event_types_cover_dual_publish() -> None:
    assert "student.question.asked" in QUESTION_EVENT_TYPES
    assert STUDENT_LECTURE_QUESTION_ASKED in QUESTION_EVENT_TYPES


def test_bucket_key_from_event() -> None:
    key = bucket_key_from_event(
        lecture_id="lec-1",
        payload={"paragraph_id": "p1", "source_chunk_id": "c1"},
    )
    assert key == QuestionBucketKey("lec-1", "p1", "c1")
    assert key.serialize() == "lec-1|p1|c1"


def test_karachi_day_bounds_are_utc() -> None:
    start, end = karachi_day_bounds(date(2026, 10, 15))
    assert start.tzinfo == timezone.utc
    assert end.tzinfo == timezone.utc
    assert (end - start).total_seconds() == 24 * 3600


def test_aggregate_nightly_fans_out_one_task_per_school() -> None:
    """Acceptance #1 + #2 — isolated apply_async per school (no shared group chord)."""
    with (
        patch(
            "app.features.next_day_review.tasks.run_db",
            return_value=["sch-a", "sch-b", "sch-c"],
        ),
        patch("app.features.next_day_review.tasks.aggregate_school.apply_async") as apply_async,
    ):
        count = aggregate_nightly(review_date="2026-10-15")

    assert count == 3
    assert apply_async.call_count == 3
    school_ids = {c.kwargs["kwargs"]["school_id"] for c in apply_async.call_args_list}
    assert school_ids == {"sch-a", "sch-b", "sch-c"}
    for call in apply_async.call_args_list:
        assert call.kwargs["kwargs"]["review_date"] == "2026-10-15"


def test_aggregate_school_task_registered_as_tenant_task() -> None:
    from app.features.next_day_review import tasks as tasks_mod

    task = getattr(tasks_mod, "aggregate_school")
    assert task.name == AGGREGATE_SCHOOL_TASK
    # Signature must include school_id for @tenant_task.
    assert "school_id" in task.run.__code__.co_varnames or "school_id" in str(
        task.run.__annotations__
    )


class _FakeResult:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def scalars(self) -> Any:
        return self

    def all(self) -> list[Any]:
        return self._rows

    def __iter__(self) -> Any:
        return iter(self._rows)


class _FakeSession:
    """Minimal async session that returns canned execute results in order."""

    def __init__(self, responses: list[Any]) -> None:
        self._responses = list(responses)

    async def execute(self, _stmt: Any) -> Any:
        return self._responses.pop(0)


def _event(
    *,
    event_id: str,
    user_id: str,
    lecture_id: str,
    paragraph_id: str | None,
    source_chunk_id: str | None,
    question_id: str,
    teacher_share: str = "share",
    event_type: str = "student.question.asked",
) -> MagicMock:
    ev = MagicMock()
    ev.id = event_id
    ev.user_id = user_id
    ev.lecture_id = lecture_id
    ev.event_type = event_type
    ev.occurred_at = datetime(2026, 10, 15, 10, 0, tzinfo=timezone.utc)
    ev.event_payload_jsonb = {
        "question_id": question_id,
        "paragraph_id": paragraph_id,
        "source_chunk_id": source_chunk_id,
        "teacher_share": teacher_share,
        "question_text": f"q-{question_id}",
        "classification": "misconception",
    }
    return ev


@pytest.mark.asyncio
async def test_aggregate_buckets_by_lecture_paragraph_chunk() -> None:
    """Acceptance #3 + #5 — GSO-scoped lectures; buckets keyed by triple."""
    lecture_ids = _FakeResult(["lec-1"])
    private_users = _FakeResult([])
    events = _FakeResult(
        [
            _event(
                event_id="e1",
                user_id="u1",
                lecture_id="lec-1",
                paragraph_id="p1",
                source_chunk_id="c1",
                question_id="q1",
            ),
            _event(
                event_id="e2",
                user_id="u2",
                lecture_id="lec-1",
                paragraph_id="p1",
                source_chunk_id="c1",
                question_id="q2",
            ),
            _event(
                event_id="e3",
                user_id="u3",
                lecture_id="lec-1",
                paragraph_id="p2",
                source_chunk_id=None,
                question_id="q3",
            ),
        ]
    )
    session = _FakeSession([lecture_ids, private_users, events])
    buckets = await aggregate_school_day(session, "sch-1", date(2026, 10, 15))  # type: ignore[arg-type]

    assert set(buckets) == {"lec-1|p1|c1", "lec-1|p2|"}
    assert len(buckets["lec-1|p1|c1"]) == 2
    assert len(buckets["lec-1|p2|"]) == 1


@pytest.mark.asyncio
async def test_aggregate_excludes_private_teacher_share() -> None:
    """Acceptance #4 — #72 opted-out students excluded."""
    lecture_ids = _FakeResult(["lec-1"])
    private_users = _FakeResult([])
    events = _FakeResult(
        [
            _event(
                event_id="e1",
                user_id="u-private",
                lecture_id="lec-1",
                paragraph_id="p1",
                source_chunk_id="c1",
                question_id="q1",
                teacher_share="private",
            ),
            _event(
                event_id="e2",
                user_id="u-share",
                lecture_id="lec-1",
                paragraph_id="p1",
                source_chunk_id="c1",
                question_id="q2",
                teacher_share="share",
            ),
        ]
    )
    session = _FakeSession([lecture_ids, private_users, events])
    buckets = await aggregate_school_day(session, "sch-1", date(2026, 10, 15))  # type: ignore[arg-type]

    assert list(buckets) == ["lec-1|p1|c1"]
    assert [item["question_id"] for item in buckets["lec-1|p1|c1"]] == ["q2"]


@pytest.mark.asyncio
async def test_aggregate_dedupes_dual_publish_alias_rows() -> None:
    lecture_ids = _FakeResult(["lec-1"])
    private_users = _FakeResult([])
    events = _FakeResult(
        [
            _event(
                event_id="e-m12",
                user_id="u1",
                lecture_id="lec-1",
                paragraph_id="p1",
                source_chunk_id="c1",
                question_id="q1",
                event_type="student.question.asked",
            ),
            _event(
                event_id="e-arch",
                user_id="u1",
                lecture_id="lec-1",
                paragraph_id="p1",
                source_chunk_id="c1",
                question_id="q1",
                event_type=STUDENT_LECTURE_QUESTION_ASKED,
            ),
        ]
    )
    session = _FakeSession([lecture_ids, private_users, events])
    buckets = await aggregate_school_day(session, "sch-1", date(2026, 10, 15))  # type: ignore[arg-type]

    assert len(buckets["lec-1|p1|c1"]) == 1


@pytest.mark.asyncio
async def test_aggregate_empty_when_no_gso_lectures() -> None:
    session = _FakeSession([_FakeResult([])])
    buckets = await aggregate_school_day(session, "sch-1", date(2026, 10, 15))  # type: ignore[arg-type]
    assert buckets == {}


@pytest.mark.asyncio
async def test_aggregate_excludes_via_user_settings_private_fallback() -> None:
    """Missing teacher_share stamp falls back to user_settings private set."""
    lecture_ids = _FakeResult(["lec-1"])
    private_users = _FakeResult(["u-private"])
    ev = _event(
        event_id="e1",
        user_id="u-private",
        lecture_id="lec-1",
        paragraph_id="p1",
        source_chunk_id="c1",
        question_id="q1",
    )
    del ev.event_payload_jsonb["teacher_share"]
    events = _FakeResult([ev])
    session = _FakeSession([lecture_ids, private_users, events])
    buckets = await aggregate_school_day(session, "sch-1", date(2026, 10, 15))  # type: ignore[arg-type]
    assert buckets == {}
