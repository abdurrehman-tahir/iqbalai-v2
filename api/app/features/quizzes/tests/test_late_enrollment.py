"""Late-enrollment quiz generation tests (T-148)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.features.lectures.models import LectureStatus
from app.features.quizzes.late_enrollment import (
    enqueue_late_quizzes_for_grade_enrollment,
    handle_student_enrolled_event,
    run_late_enrollment_quiz_generation,
)


@pytest.mark.asyncio
async def test_late_enrollment_skips_duplicates(monkeypatch: pytest.MonkeyPatch) -> None:
    session = AsyncMock()
    lecture = SimpleNamespace(
        id="lec-1",
        current_version_id="ver-1",
        status=LectureStatus.PUBLISHED,
    )

    class _Lectures:
        def scalars(self):
            return self

        def all(self):
            return [lecture]

    class _Existing:
        def scalar_one_or_none(self):
            return "quiz-existing"

    session.execute = AsyncMock(side_effect=[_Lectures(), _Existing()])

    apply_async = MagicMock()
    monkeypatch.setattr(
        "app.features.quizzes.tasks.generate_quiz_for_student.apply_async",
        apply_async,
    )

    count = await run_late_enrollment_quiz_generation(
        session,
        school_id="sch-1",
        student_user_id="stu-new",
        grade_subject_offering_id="off-1",
    )
    assert count == 0
    apply_async.assert_not_called()


@pytest.mark.asyncio
async def test_late_enrollment_enqueues_for_published(monkeypatch: pytest.MonkeyPatch) -> None:
    session = AsyncMock()
    lecture = SimpleNamespace(
        id="lec-1",
        current_version_id="ver-1",
        status=LectureStatus.PUBLISHED,
    )

    class _Lectures:
        def scalars(self):
            return self

        def all(self):
            return [lecture]

    class _Existing:
        def scalar_one_or_none(self):
            return None

    session.execute = AsyncMock(side_effect=[_Lectures(), _Existing()])

    apply_async = MagicMock()
    monkeypatch.setattr(
        "app.features.quizzes.tasks.generate_quiz_for_student.apply_async",
        apply_async,
    )

    count = await run_late_enrollment_quiz_generation(
        session,
        school_id="sch-1",
        student_user_id="stu-new",
        grade_subject_offering_id="off-1",
    )
    assert count == 1
    apply_async.assert_called_once()


@pytest.mark.asyncio
async def test_grade_fanout_enqueues_per_offering(monkeypatch: pytest.MonkeyPatch) -> None:
    session = AsyncMock()

    class _FakeOfferings:
        async def list_by_grade(self, grade_id: str):
            return [SimpleNamespace(id="off-1"), SimpleNamespace(id="off-2")]

    monkeypatch.setattr(
        "app.features.quizzes.late_enrollment.OfferingRepository",
        lambda session: _FakeOfferings(),
    )
    apply_async = MagicMock()
    monkeypatch.setattr(
        "app.features.quizzes.tasks.generate_for_late_enrollment.apply_async",
        apply_async,
    )

    count = await enqueue_late_quizzes_for_grade_enrollment(
        session,
        school_id="sch-1",
        student_user_id="stu-1",
        grade_id="grade-1",
    )
    assert count == 2
    assert apply_async.call_count == 2


@pytest.mark.asyncio
async def test_handle_student_enrolled_skips_independent() -> None:
    await handle_student_enrolled_event(
        {
            "tenant_type": "independent",
            "payload": {"student_user_id": "x", "school_id": "y"},
        }
    )
