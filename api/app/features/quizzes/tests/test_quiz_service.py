"""Quiz service unit tests — T-145/T-146/T-147."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.core.exceptions import NotFoundError, ValidationError
from app.features.lectures.models import LectureStatus
from app.features.quizzes.api_schemas import QuizSubmitRequest
from app.features.quizzes.models import QuizAssignmentStatus
from app.features.quizzes.service import QuizService
from app.features.users.models import UserRole


def _user(*, role: UserRole = UserRole.STUDENT, user_id: str = "stu-1", school_id: str = "sch-1"):
    return SimpleNamespace(
        id=user_id,
        role=role,
        school_id=school_id,
        deleted_at=None,
        display_name="Student One",
        authentik_id="auth-stu",
    )


@pytest.mark.asyncio
async def test_list_my_quizzes_only_own_published(monkeypatch: pytest.MonkeyPatch) -> None:
    session = AsyncMock()
    svc = QuizService(session)
    user = _user()

    async def _require(claims: dict[str, object]):
        return user

    monkeypatch.setattr(svc, "_require_user", _require)

    assignment = SimpleNamespace(
        id="asg-1",
        status=QuizAssignmentStatus.PUBLISHED,
        assigned_at=datetime.now(timezone.utc),
    )
    quiz = SimpleNamespace(id="quiz-1")
    lecture = SimpleNamespace(
        id="lec-1",
        topic="Newton",
        title="Forces",
        status=LectureStatus.PUBLISHED,
    )

    class _Result:
        def all(self):
            return [(assignment, quiz, lecture)]

        def scalar_one(self):
            return 5

    session.execute = AsyncMock(side_effect=[_Result(), _Result()])

    cards = await svc.list_my_quizzes({"sub": "auth-stu"})
    assert len(cards) == 1
    assert cards[0].assignment_id == "asg-1"
    assert cards[0].question_count == 5
    assert cards[0].lecture_topic == "Newton"


@pytest.mark.asyncio
async def test_submit_is_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    session = AsyncMock()
    svc = QuizService(session)
    user = _user()

    async def _require(claims: dict[str, object]):
        return user

    monkeypatch.setattr(svc, "_require_user", _require)

    assignment = SimpleNamespace(
        id="asg-1",
        quiz_id="quiz-1",
        student_user_id="stu-1",
        status=QuizAssignmentStatus.COMPLETED,
        deleted_at=None,
    )
    quiz = SimpleNamespace(id="quiz-1", lecture_id="lec-1", deleted_at=None)
    lecture = SimpleNamespace(id="lec-1", status=LectureStatus.PUBLISHED)
    existing = SimpleNamespace(
        id="att-1",
        score=3,
        max_score=5,
        answers_jsonb={"q1": "A"},
    )

    async def _owned(u, aid):
        return assignment, quiz, lecture

    monkeypatch.setattr(svc, "_owned_assignment", _owned)

    class _AttemptResult:
        def scalar_one_or_none(self):
            return existing

    session.execute = AsyncMock(return_value=_AttemptResult())

    async def _result_from_attempt(a, q, att):
        from app.features.quizzes.api_schemas import QuizAttemptResultRead

        return QuizAttemptResultRead(
            assignment_id=a.id,
            attempt_id=att.id,
            score=att.score,
            max_score=att.max_score,
            status=a.status.value,
            questions=[],
        )

    monkeypatch.setattr(svc, "_result_from_attempt", _result_from_attempt)

    first = await svc.submit_my_quiz({"sub": "x"}, "asg-1", QuizSubmitRequest(answers={"q1": "A"}))
    second = await svc.submit_my_quiz({"sub": "x"}, "asg-1", QuizSubmitRequest(answers={"q1": "B"}))
    assert first.attempt_id == second.attempt_id == "att-1"
    assert first.score == 3


@pytest.mark.asyncio
async def test_submit_rejects_pending(monkeypatch: pytest.MonkeyPatch) -> None:
    session = AsyncMock()
    svc = QuizService(session)
    user = _user()

    async def _require(claims: dict[str, object]):
        return user

    monkeypatch.setattr(svc, "_require_user", _require)

    assignment = SimpleNamespace(
        id="asg-1",
        status=QuizAssignmentStatus.PENDING,
        student_user_id="stu-1",
        deleted_at=None,
    )
    quiz = SimpleNamespace(id="quiz-1", lecture_id="lec-1", deleted_at=None)
    lecture = SimpleNamespace(id="lec-1")

    async def _owned(u, aid):
        return assignment, quiz, lecture

    monkeypatch.setattr(svc, "_owned_assignment", _owned)

    with pytest.raises(ValidationError):
        await svc.submit_my_quiz({"sub": "x"}, "asg-1", QuizSubmitRequest(answers={}))


@pytest.mark.asyncio
async def test_get_my_quiz_hides_unpublished_lecture(monkeypatch: pytest.MonkeyPatch) -> None:
    session = AsyncMock()
    svc = QuizService(session)
    user = _user()

    async def _require(claims: dict[str, object]):
        return user

    monkeypatch.setattr(svc, "_require_user", _require)

    assignment = SimpleNamespace(
        id="asg-1",
        status=QuizAssignmentStatus.PUBLISHED,
        student_user_id="stu-1",
        deleted_at=None,
    )
    quiz = SimpleNamespace(id="quiz-1", deleted_at=None)
    lecture = SimpleNamespace(id="lec-1", status=LectureStatus.READY_FOR_PUBLISH)

    async def _owned(u, aid):
        return assignment, quiz, lecture

    monkeypatch.setattr(svc, "_owned_assignment", _owned)

    with pytest.raises(NotFoundError):
        await svc.get_my_quiz({"sub": "x"}, "asg-1")
