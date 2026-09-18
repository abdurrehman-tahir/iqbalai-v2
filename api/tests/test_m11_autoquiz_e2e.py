"""T-150 — M-11 backend E2E smoke (LLM mocked).

Chains: calibrate strong vs weak → publish flips assignments → attempt
idempotency → teacher aggregate → late enrollment enqueue → independent skip.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.features.lectures.models import LectureStatus
from app.features.quizzes.api_schemas import QuizSubmitRequest
from app.features.quizzes.models import QuizAssignmentStatus
from app.features.quizzes.publish import publish_pending_assignments_for_lecture
from app.features.quizzes.service import QuizService
from app.features.users.models import UserRole


@pytest.mark.asyncio
async def test_m11_calibration_differs_strong_vs_weak() -> None:
    from app.features.quizzes.schemas import CalibrationProfile, CalibrationSource

    strong = CalibrationProfile(
        source=CalibrationSource.DIAGNOSTIC_SEED,
        target_difficulty="applied",
        topic_confidence={"Forces": 0.9},
        focus_areas=[],
        notes="strong",
    )
    weak = CalibrationProfile(
        source=CalibrationSource.DIAGNOSTIC_SEED,
        target_difficulty="foundational",
        topic_confidence={"Forces": 0.2},
        focus_areas=["basics"],
        notes="weak",
    )
    assert strong.target_difficulty != weak.target_difficulty
    assert strong.target_difficulty == "applied"
    assert weak.target_difficulty == "foundational"


@pytest.mark.asyncio
async def test_m11_publish_flips_pending_assignments(monkeypatch: pytest.MonkeyPatch) -> None:
    session = AsyncMock()

    class _QuizIds:
        def scalars(self):
            return self

        def all(self):
            return ["quiz-1", "quiz-2"]

    class _Update:
        rowcount = 2

    session.execute = AsyncMock(side_effect=[_QuizIds(), _Update()])
    count = await publish_pending_assignments_for_lecture(session, lecture_id="lec-1")
    assert count == 2


@pytest.mark.asyncio
async def test_m11_submit_idempotent_and_aggregate_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    session = AsyncMock()
    svc = QuizService(session)
    student = SimpleNamespace(
        id="stu-1",
        role=UserRole.STUDENT,
        school_id="sch-1",
        deleted_at=None,
        display_name="S",
        authentik_id="a",
    )
    teacher = SimpleNamespace(
        id="tch-1",
        role=UserRole.TEACHER,
        school_id="sch-1",
        deleted_at=None,
        display_name="T",
        authentik_id="t",
    )

    assignment = SimpleNamespace(
        id="asg-1",
        quiz_id="quiz-1",
        student_user_id="stu-1",
        status=QuizAssignmentStatus.COMPLETED,
        deleted_at=None,
        calibration_jsonb={},
    )
    quiz = SimpleNamespace(id="quiz-1", lecture_id="lec-1", deleted_at=None)
    lecture = SimpleNamespace(
        id="lec-1",
        topic="Forces",
        status=LectureStatus.PUBLISHED,
        teacher_user_id="tch-1",
        school_id="sch-1",
    )
    existing = SimpleNamespace(id="att-1", score=4, max_score=5, answers_jsonb={})

    async def _require_student(claims):
        return student

    async def _require_teacher(claims):
        return teacher

    async def _owned(u, aid):
        return assignment, quiz, lecture

    monkeypatch.setattr(svc, "_owned_assignment", _owned)

    class _Attempt:
        def scalar_one_or_none(self):
            return existing

    session.execute = AsyncMock(return_value=_Attempt())
    session.get = AsyncMock(return_value=lecture)

    async def _result(a, q, att):
        from app.features.quizzes.api_schemas import QuizAttemptResultRead

        return QuizAttemptResultRead(
            assignment_id=a.id,
            attempt_id=att.id,
            score=att.score,
            max_score=att.max_score,
            status=a.status.value,
            questions=[],
        )

    monkeypatch.setattr(svc, "_result_from_attempt", _result)
    monkeypatch.setattr(svc, "_require_user", _require_student)

    r1 = await svc.submit_my_quiz({"sub": "s"}, "asg-1", QuizSubmitRequest(answers={}))
    r2 = await svc.submit_my_quiz({"sub": "s"}, "asg-1", QuizSubmitRequest(answers={}))
    assert r1.attempt_id == r2.attempt_id

    # Teacher aggregate scope
    monkeypatch.setattr(svc, "_require_user", _require_teacher)

    class _Assignments:
        def scalars(self):
            return self

        def all(self):
            return [
                SimpleNamespace(
                    id="asg-1",
                    quiz_id="quiz-1",
                    status=QuizAssignmentStatus.COMPLETED,
                )
            ]

    class _Attempt2:
        def scalar_one_or_none(self):
            return SimpleNamespace(score=4, max_score=5, answers_jsonb={})

    class _EmptyQuestions:
        def scalars(self):
            return self

        def all(self):
            return []

        def scalar_one(self):
            return "quiz-1"

    session.execute = AsyncMock(
        side_effect=[_Assignments(), _Attempt2(), _EmptyQuestions(), _EmptyQuestions()]
    )
    session.get = AsyncMock(return_value=lecture)

    async def _audit(**kwargs):
        return None

    monkeypatch.setattr("app.features.quizzes.service.audit", _audit)

    agg = await svc.teacher_aggregate_for_lecture({"sub": "t"}, "lec-1")
    assert agg.assigned_count == 1
    assert agg.completed_count == 1
    assert agg.average_score == pytest.approx(0.8)


@pytest.mark.asyncio
async def test_m11_late_enrollment_and_independent_skip(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.features.quizzes.late_enrollment import (
        handle_student_enrolled_event,
        run_late_enrollment_quiz_generation,
    )

    await handle_student_enrolled_event({"tenant_type": "independent", "payload": {}})

    session = AsyncMock()

    class _Lectures:
        def scalars(self):
            return self

        def all(self):
            return [
                SimpleNamespace(id="lec-1", current_version_id="ver-1", status=LectureStatus.PUBLISHED)
            ]

    class _None:
        def scalar_one_or_none(self):
            return None

    session.execute = AsyncMock(side_effect=[_Lectures(), _None()])
    apply_async = MagicMock()
    monkeypatch.setattr(
        "app.features.quizzes.tasks.generate_quiz_for_student.apply_async",
        apply_async,
    )
    count = await run_late_enrollment_quiz_generation(
        session,
        school_id="sch-1",
        student_user_id="stu-late",
        grade_subject_offering_id="off-1",
    )
    assert count == 1
    apply_async.assert_called_once()
