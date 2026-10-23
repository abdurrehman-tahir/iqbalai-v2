"""T-202 — reflective coaching prompt generation + teacher response storage."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from app.core.exceptions import PermissionDeniedError, ValidationError
from app.features.next_day_review import reflection
from app.features.next_day_review.categories import REFLECTIVE_RESPONSE_PATTERN
from app.features.next_day_review.reflection import (
    REFLECTIVE_WEAKNESS_TYPE,
    generate_reflective_prompt,
    record_reflection,
)
from app.features.next_day_review.schemas import ReviewClusterSnapshot
from app.features.next_day_review.service import ACTION_REFLECT, NextDayReviewService
from app.features.next_day_review.tests.conftest import World, make_snapshot, make_user
from app.features.teacher_coaching.models import SchoolTeacherAiMemory, TeacherResponseType
from app.features.users.models import UserRole

SNAPS = [ReviewClusterSnapshot.model_validate(make_snapshot("a"))]
_KW: dict[str, str] = {
    "offering_label": "Grade 9 Physics",
    "lecture_topic": "Newton's third law",
    "target_language": "en",
}


@pytest.mark.asyncio
async def test_generates_question_grounded_in_clusters(monkeypatch: pytest.MonkeyPatch) -> None:
    chat = AsyncMock(return_value='{"question": "Would a tug-of-war demo make the pair concrete?"}')
    monkeypatch.setattr(reflection, "chat", chat)
    q = await generate_reflective_prompt(SNAPS, **_KW)
    assert q == "Would a tug-of-war demo make the pair concrete?"
    assert chat.await_args is not None
    assert "Why a?" in chat.await_args.args[0][1]["content"]


@pytest.mark.asyncio
async def test_grading_language_retried_then_omitted(monkeypatch: pytest.MonkeyPatch) -> None:
    chat = AsyncMock(return_value='{"question": "Why was your explanation so poor?"}')
    monkeypatch.setattr(reflection, "chat", chat)
    assert await generate_reflective_prompt(SNAPS, **_KW) == ""
    assert chat.await_count == 2


@pytest.mark.asyncio
async def test_grading_then_coaching_uses_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    chat = AsyncMock(
        side_effect=[
            '{"question": "You should have drawn a diagram, right?"}',
            '{"question": "Could a diagram of both bodies help tomorrow?"}',
        ]
    )
    monkeypatch.setattr(reflection, "chat", chat)
    assert await generate_reflective_prompt(SNAPS, **_KW) == (
        "Could a diagram of both bodies help tomorrow?"
    )


@pytest.mark.asyncio
async def test_llm_failure_omits_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(reflection, "chat", AsyncMock(side_effect=RuntimeError("down")))
    assert await generate_reflective_prompt(SNAPS, **_KW) == ""


class _FakeMemoryRepo:
    row: SchoolTeacherAiMemory | None = None
    created: list[SchoolTeacherAiMemory] = []

    def __init__(self, _session: Any) -> None:
        pass

    async def get_by_weakness(self, **kw: str) -> SchoolTeacherAiMemory | None:
        assert kw["category"] == REFLECTIVE_RESPONSE_PATTERN
        return _FakeMemoryRepo.row

    async def create(self, memory: SchoolTeacherAiMemory) -> SchoolTeacherAiMemory:
        _FakeMemoryRepo.created.append(memory)
        return memory

    async def update(self, memory: SchoolTeacherAiMemory) -> SchoolTeacherAiMemory:
        return memory


@pytest.fixture
def memory_repo(monkeypatch: pytest.MonkeyPatch) -> type[_FakeMemoryRepo]:
    _FakeMemoryRepo.row = None
    _FakeMemoryRepo.created = []
    monkeypatch.setattr(reflection, "SchoolTeacherAiMemoryRepository", _FakeMemoryRepo)
    return _FakeMemoryRepo


@pytest.mark.asyncio
async def test_record_reflection_creates_pattern_row(memory_repo: type[_FakeMemoryRepo]) -> None:
    row = await record_reflection(
        AsyncMock(), teacher_user_id="teacher-1", prompt="Q?", response="I'll use a demo."
    )
    assert memory_repo.created == [row]
    assert row.category == REFLECTIVE_RESPONSE_PATTERN
    assert row.weakness_type == REFLECTIVE_WEAKNESS_TYPE
    assert row.teacher_response == TeacherResponseType.ACTED
    assert "I'll use a demo." in row.last_suggestion


@pytest.mark.asyncio
async def test_record_reflection_bumps_existing(memory_repo: type[_FakeMemoryRepo]) -> None:
    memory_repo.row = SchoolTeacherAiMemory(
        teacher_user_id="teacher-1",
        category=REFLECTIVE_RESPONSE_PATTERN,
        weakness_type=REFLECTIVE_WEAKNESS_TYPE,
        frequency=2,
        last_suggestion="old",
        teacher_response=TeacherResponseType.ACTED,
    )
    row = await record_reflection(
        AsyncMock(), teacher_user_id="teacher-1", prompt="Q2?", response="New answer"
    )
    assert row.frequency == 3
    assert "New answer" in row.last_suggestion
    assert memory_repo.created == []


@pytest.mark.asyncio
async def test_owner_reflects_and_action_recorded(
    world: World, as_user: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    record = AsyncMock()
    monkeypatch.setattr("app.features.next_day_review.service.record_reflection", record)
    monkeypatch.setattr(
        "app.features.next_day_review.service._offering_label", AsyncMock(return_value="G9")
    )
    claims = as_user(world.teacher)
    service = NextDayReviewService(world.session())
    service._student_names = AsyncMock(return_value={})  # type: ignore[method-assign]

    detail = await service.reflect(claims, "rev-1", "  I will try a demo.  ")

    assert record.await_args is not None
    assert record.await_args.kwargs["response"] == "I will try a demo."
    assert detail.reflected is True
    assert ACTION_REFLECT in world.review.acted_actions
    assert world.review.pending_action is False


@pytest.mark.asyncio
async def test_school_admin_cannot_reflect_for_teacher(world: World, as_user: Any) -> None:
    claims = as_user(make_user(UserRole.SCHOOL_ADMIN, "admin-1"))
    with pytest.raises(PermissionDeniedError):
        await NextDayReviewService(world.session()).reflect(claims, "rev-1", "x")


@pytest.mark.asyncio
async def test_reflect_without_prompt_is_rejected(world: World, as_user: Any) -> None:
    world.review.reflective_prompt = ""
    claims = as_user(world.teacher)
    with pytest.raises(ValidationError):
        await NextDayReviewService(world.session()).reflect(claims, "rev-1", "x")
