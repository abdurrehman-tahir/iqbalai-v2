"""T-200 — review card assembly, 05:00 SLA alert, 06:00 teacher notify."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.features.lectures.models import SchoolLecture
from app.features.next_day_review import assembly
from app.features.next_day_review.assembly import (
    assemble_reviews,
    build_snapshot,
    check_sla,
    notify_not_before,
    notify_ready_reviews,
    previous_review_date,
    sla_deadline,
)
from app.features.next_day_review.classification import ClassifiedCluster
from app.features.next_day_review.models import LectureReview, LectureReviewStatus
from app.features.next_day_review.tasks import CHECK_SLA_TASK, NOTIFY_READY_TASK
from app.tasks.beat_schedule import BEAT_SCHEDULE

REVIEW_DATE = date(2026, 10, 22)


@pytest.fixture(autouse=True)
def _no_reflective_llm(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    """The reflective prompt (T-202) is its own LLM call — never reach the network."""
    mock = AsyncMock(return_value="Would a worked example help?")
    monkeypatch.setattr(assembly, "generate_reflective_prompt", mock)
    return mock


def _cluster(
    ref: str,
    *,
    lecture_id: str = "lec-1",
    gso_id: str | None = "gso-1",
    students: int = 3,
    critical: bool = False,
    frequent: bool = True,
    error: str | None = None,
) -> ClassifiedCluster:
    items = [
        {
            "question_id": f"{ref}-q{i}",
            "user_id": f"stu-{i}",
            "lecture_id": lecture_id,
            "paragraph_id": "p1",
            "source_chunk_id": "c1",
            "question_text": f"Why does {ref} happen? ({i})",
            "occurred_at": "2026-10-22T10:00:00+00:00",
        }
        for i in range(students)
    ]
    return ClassifiedCluster(
        cluster_ref=ref,
        bucket_key="lec-1|p1|c1",
        items=items,
        unique_student_count=students,
        roster_size=30,
        freq_score=students / 3,
        frequency_qualifies=frequent,
        criticality=8 if critical else (None if error else 3),
        criticality_qualifies=critical,
        qualifies_for_mini_lecture=frequent or critical,
        gso_id=gso_id,
        error=error,
    )


class _Result:
    def __init__(self, scalar: Any = None, rows: list[Any] | None = None) -> None:
        self._scalar = scalar
        self._rows = rows or []

    def scalar_one_or_none(self) -> Any:
        return self._scalar

    def first(self) -> Any:
        return ("Grade 9", "Physics")

    def all(self) -> list[Any]:
        return self._rows

    def scalars(self) -> Any:
        rows = self._rows
        return MagicMock(all=lambda: rows)


def _session(lecture: SchoolLecture, existing: LectureReview | None = None) -> MagicMock:
    session = MagicMock()

    async def _get(model: type[Any], pk: str) -> Any:
        if model is SchoolLecture and pk == lecture.id:
            return lecture
        return None

    async def _execute(stmt: Any) -> _Result:
        return _Result(scalar=existing)

    session.get = AsyncMock(side_effect=_get)
    session.execute = AsyncMock(side_effect=_execute)
    session.commit = AsyncMock()
    session.add = MagicMock()
    return session


def _lecture() -> SchoolLecture:
    return SchoolLecture(
        id="lec-1",
        school_id="school-1",
        teacher_user_id="teacher-1",
        title="Newton's Laws",
        topic="Newton's third law",
        grade_subject_offering_id="gso-1",
    )


# --- snapshot -------------------------------------------------------------------


def test_snapshot_routes_critical_and_frequency_columns() -> None:
    crit = build_snapshot(_cluster("a", critical=True, frequent=False), "mini-1")
    freq = build_snapshot(_cluster("b"), None)
    assert crit is not None and crit.column == "critical"
    assert crit.mini_lecture_id == "mini-1"
    assert freq is not None and freq.column == "high_frequency"
    assert freq.question_count == 3
    assert {q.student_user_id for q in freq.questions} == {"stu-0", "stu-1", "stu-2"}
    assert freq.representative_question.startswith("Why does b happen")


def test_snapshot_skips_non_qualifying_cluster() -> None:
    assert build_snapshot(_cluster("c", frequent=False), None) is None


# --- assembly -------------------------------------------------------------------


@pytest.mark.asyncio
async def test_assembles_one_review_per_gso_with_summary_clusters_and_mini(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        assembly, "chat", AsyncMock(return_value='{"summary": "Students mixed up forces."}')
    )
    session = _session(_lecture())
    clusters = [
        _cluster("a", critical=True),
        _cluster("b"),
        # DLQ'd on criticality but frequency-qualified — still ships (acceptance #4).
        _cluster("d", error="TimeoutError: llm"),
        _cluster("e", gso_id=None),
    ]
    minis = [{"cluster_ref": "a", "lecture_id": "mini-1", "status": "generated"}]

    reviews = await assemble_reviews(
        session, school_id="school-1", review_date=REVIEW_DATE, clusters=clusters, minis=minis
    )

    assert len(reviews) == 1
    review = reviews[0]
    assert review.gso_id == "gso-1"
    assert review.lecture_id == "lec-1"
    assert review.ai_summary == "Students mixed up forces."
    assert review.reflective_prompt == "Would a worked example help?"
    assert review.mini_lecture_id == "mini-1"
    assert review.pending_action is True
    assert review.status == LectureReviewStatus.PENDING
    assert review.generated_at is not None
    refs = [c["cluster_ref"] for c in review.clusters_jsonb]
    assert refs[0] == "a"  # critical first
    assert set(refs) == {"a", "b", "d"}
    session.add.assert_called_once_with(review)
    session.commit.assert_awaited()


@pytest.mark.asyncio
async def test_summary_failure_still_ships_card(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(assembly, "chat", AsyncMock(side_effect=RuntimeError("llm down")))
    session = _session(_lecture())
    reviews = await assemble_reviews(
        session, school_id="school-1", review_date=REVIEW_DATE, clusters=[_cluster("a")], minis=[]
    )
    assert len(reviews) == 1
    assert reviews[0].ai_summary == ""
    assert len(reviews[0].clusters_jsonb) == 1


@pytest.mark.asyncio
async def test_rerun_leaves_engaged_card_untouched(monkeypatch: pytest.MonkeyPatch) -> None:
    chat = AsyncMock(return_value='{"summary": "new"}')
    monkeypatch.setattr(assembly, "chat", chat)
    engaged = LectureReview(
        lecture_id="lec-1",
        gso_id="gso-1",
        review_date=REVIEW_DATE,
        ai_summary="old",
        pending_action=False,
    )
    session = _session(_lecture(), existing=engaged)
    reviews = await assemble_reviews(
        session, school_id="school-1", review_date=REVIEW_DATE, clusters=[_cluster("a")], minis=[]
    )
    assert reviews == [engaged]
    assert engaged.ai_summary == "old"
    chat.assert_not_awaited()
    session.add.assert_not_called()


# --- timing ---------------------------------------------------------------------


def test_sla_and_notify_times_are_morning_after_in_karachi() -> None:
    assert sla_deadline(REVIEW_DATE).isoformat() == "2026-10-23T05:00:00+05:00"
    assert notify_not_before(REVIEW_DATE).isoformat() == "2026-10-23T06:00:00+05:00"
    # 01:00 UTC on the 23rd is 06:00 PKT → reviewing the 22nd.
    assert previous_review_date(datetime(2026, 10, 23, 1, 0, tzinfo=timezone.utc)) == REVIEW_DATE


def test_beat_runs_sla_at_0500_and_notify_at_0600_karachi() -> None:
    sla: Any = BEAT_SCHEDULE["review-check-sla"]
    notify: Any = BEAT_SCHEDULE["review-notify-ready"]
    assert sla["task"] == CHECK_SLA_TASK
    assert sla["schedule"].hour == {0}
    assert notify["task"] == NOTIFY_READY_TASK
    assert notify["schedule"].hour == {1}
    assert notify["schedule"].minute == {0}


# --- SLA --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sla_breach_alerts_platform_admins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(assembly, "_schools_with_questions", AsyncMock(return_value={"s1", "s2"}))
    monkeypatch.setattr(assembly, "_schools_with_reviews", AsyncMock(return_value={"s1"}))
    notify = AsyncMock()
    audit = AsyncMock()
    monkeypatch.setattr(assembly, "notify_all_platform_admins", notify)
    monkeypatch.setattr(assembly, "audit", audit)
    session = MagicMock(commit=AsyncMock())

    missing = await check_sla(session, review_date=REVIEW_DATE)

    assert missing == ["s2"]
    notify.assert_awaited_once()
    assert notify.await_args is not None
    assert notify.await_args.kwargs["template_key"] == "system.review_sla_breach"
    assert notify.await_args.kwargs["params"]["count"] == "1"
    audit.assert_awaited_once()


@pytest.mark.asyncio
async def test_sla_met_sends_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(assembly, "_schools_with_questions", AsyncMock(return_value={"s1"}))
    monkeypatch.setattr(assembly, "_schools_with_reviews", AsyncMock(return_value={"s1"}))
    notify = AsyncMock()
    monkeypatch.setattr(assembly, "notify_all_platform_admins", notify)
    assert await check_sla(MagicMock(), review_date=REVIEW_DATE) == []
    notify.assert_not_awaited()


# --- 06:00 notify -------------------------------------------------------------------


@pytest.mark.asyncio
async def test_notify_refuses_before_0600_karachi(monkeypatch: pytest.MonkeyPatch) -> None:
    notify = AsyncMock()
    monkeypatch.setattr(assembly, "notify_lecture_event", notify)
    session = MagicMock(execute=AsyncMock())
    early = datetime(2026, 10, 23, 0, 59, tzinfo=timezone.utc)  # 05:59 PKT
    assert await notify_ready_reviews(session, review_date=REVIEW_DATE, now=early) == 0
    session.execute.assert_not_awaited()
    notify.assert_not_awaited()


@pytest.mark.asyncio
async def test_notify_sends_once_and_stamps_notified_at(monkeypatch: pytest.MonkeyPatch) -> None:
    review = LectureReview(lecture_id="lec-1", gso_id="gso-1", review_date=REVIEW_DATE)
    lecture = _lecture()
    notify = AsyncMock()
    monkeypatch.setattr(assembly, "notify_lecture_event", notify)
    monkeypatch.setattr(assembly, "_resolve_recipient", AsyncMock(return_value=("ak-1", "ur")))
    session = MagicMock(
        execute=AsyncMock(return_value=_Result(rows=[(review, lecture)])), commit=AsyncMock()
    )
    at_six = datetime(2026, 10, 23, 1, 0, tzinfo=timezone.utc)

    sent = await notify_ready_reviews(session, review_date=REVIEW_DATE, now=at_six)

    assert sent == 1
    assert review.notified_at == at_six
    assert notify.await_args is not None
    assert notify.await_args.kwargs["template_key"] == "lectures.next_day_review_ready"
    assert notify.await_args.kwargs["locale"] == "ur"
    assert notify.await_args.kwargs["recipient_user_id"] == "ak-1"
