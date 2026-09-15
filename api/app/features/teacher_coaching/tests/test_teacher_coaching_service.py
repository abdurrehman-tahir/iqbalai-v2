"""T-138 — Teaching Innovation Record service tests (Flow 5 §3.10 #36).

Covers the adaptive lifecycle directly:
1. first detection -> a suggestion is generated and stored
2. still-pending recurrence -> frequency bumps silently, no new LLM call
3. a response (acted/ignored) closes a round -> next recurrence regenerates
4. non-weak scores never create a row
5. one dimension's LLM failure never blocks tracking the others
6. respond/list/resolve helpers
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock

import pytest

from app.core.exceptions import NotFoundError, PermissionDeniedError, ValidationError
from app.features.independent_users.models import (
    IndependentUser,
    IndependentUserAccountStatus,
    IndependentUserRole,
)
from app.features.teacher_coaching import service
from app.features.teacher_coaching.models import (
    IndependentTeacherAiMemory,
    SchoolTeacherAiMemory,
    TeacherResponseType,
)
from app.features.users.models import User, UserAccountStatus, UserRole

_VALID_SUGGESTION_JSON = '{"suggestion": "Try opening with a local, everyday example."}'


def _memory_row(**overrides: Any) -> SchoolTeacherAiMemory:
    defaults: dict[str, Any] = dict(
        teacher_user_id="teacher-1",
        category="quality_dimension",
        weakness_type="originality",
        frequency=1,
        last_suggestion="Try grounding in local Punjab examples.",
        teacher_response=TeacherResponseType.NONE,
    )
    defaults.update(overrides)
    row = SchoolTeacherAiMemory(**defaults)
    row.updated_at = datetime.now(timezone.utc)
    return row


class _FakeSchoolRepo:
    def __init__(self, _session: Any) -> None:
        pass

    store: dict[str, SchoolTeacherAiMemory] = {}
    created: list[SchoolTeacherAiMemory] = []
    updated: list[SchoolTeacherAiMemory] = []

    async def get_by_weakness(
        self, *, teacher_user_id: str, category: str, weakness_type: str
    ) -> SchoolTeacherAiMemory | None:
        return next(
            (
                r
                for r in self.store.values()
                if r.teacher_user_id == teacher_user_id
                and r.category == category
                and r.weakness_type == weakness_type
            ),
            None,
        )

    async def create(self, memory: SchoolTeacherAiMemory) -> SchoolTeacherAiMemory:
        self.store[memory.id] = memory
        self.__class__.created.append(memory)
        return memory

    async def update(self, memory: SchoolTeacherAiMemory) -> SchoolTeacherAiMemory:
        self.__class__.updated.append(memory)
        return memory

    async def get_by_id(self, memory_id: str) -> SchoolTeacherAiMemory | None:
        return self.store.get(memory_id)

    async def list_pending_for_teacher(self, teacher_user_id: str) -> list[SchoolTeacherAiMemory]:
        return [
            r
            for r in self.store.values()
            if r.teacher_user_id == teacher_user_id
            and r.teacher_response == TeacherResponseType.NONE
        ]


@pytest.fixture(autouse=True)
def _reset_fake_repo() -> None:
    _FakeSchoolRepo.store = {}
    _FakeSchoolRepo.created = []
    _FakeSchoolRepo.updated = []


@pytest.fixture(autouse=True)
def _mock_coaching_notifications(monkeypatch: pytest.MonkeyPatch) -> None:
    """T-140: every new-suggestion path fires a best-effort notification —
    mocked here so no real notify_lecture_event/DB call runs inside these
    unit tests (the notify functions have their own dedicated tests)."""
    monkeypatch.setattr(
        "app.features.teacher_coaching.service._notify_coaching_suggestion_school", AsyncMock()
    )
    monkeypatch.setattr(
        "app.features.teacher_coaching.service._notify_coaching_suggestion_independent",
        AsyncMock(),
    )


def test_is_weak_below_half_of_cap() -> None:
    assert service._is_weak("originality", 4) is True  # cap 10, half=5
    assert service._is_weak("originality", 5) is False
    assert service._is_weak("cultural_relevance", 2) is True  # cap 5, half=2.5
    assert service._is_weak("cultural_relevance", 3) is False


def test_is_weak_unknown_dimension_or_non_int_is_false() -> None:
    assert service._is_weak("ai_learning", 0) is False  # excluded dimension
    assert service._is_weak("originality", None) is False


@pytest.mark.asyncio
async def test_first_detection_creates_row_with_generated_suggestion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.features.teacher_coaching.service.SchoolTeacherAiMemoryRepository", _FakeSchoolRepo
    )
    monkeypatch.setattr(
        "app.features.teacher_coaching.service.chat", AsyncMock(return_value=_VALID_SUGGESTION_JSON)
    )

    await service.detect_and_track_weakness_school(
        AsyncMock(),
        teacher_user_id="teacher-1",
        scores={
            "originality": 3,
            "depth": 9,
            "cultural_relevance": 4,
            "engagement": 4,
            "alignment": 9,
        },
        region="Punjab",
    )

    assert len(_FakeSchoolRepo.created) == 1
    created = _FakeSchoolRepo.created[0]
    assert created.weakness_type == "originality"
    assert created.frequency == 1
    assert created.last_suggestion == "Try opening with a local, everyday example."
    assert created.teacher_response == TeacherResponseType.NONE


@pytest.mark.asyncio
async def test_non_weak_scores_never_create_a_row(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.features.teacher_coaching.service.SchoolTeacherAiMemoryRepository", _FakeSchoolRepo
    )
    chat_mock = AsyncMock(return_value=_VALID_SUGGESTION_JSON)
    monkeypatch.setattr("app.features.teacher_coaching.service.chat", chat_mock)

    await service.detect_and_track_weakness_school(
        AsyncMock(),
        teacher_user_id="teacher-1",
        scores={
            "originality": 9,
            "depth": 9,
            "cultural_relevance": 4,
            "engagement": 4,
            "alignment": 9,
        },
        region=None,
    )

    assert _FakeSchoolRepo.created == []
    chat_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_still_pending_recurrence_bumps_frequency_silently(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Acceptance-adjacent: no suggestion spam while one is unactioned."""
    existing = _memory_row(frequency=1, teacher_response=TeacherResponseType.NONE)
    _FakeSchoolRepo.store = {existing.id: existing}
    monkeypatch.setattr(
        "app.features.teacher_coaching.service.SchoolTeacherAiMemoryRepository", _FakeSchoolRepo
    )
    chat_mock = AsyncMock(return_value=_VALID_SUGGESTION_JSON)
    monkeypatch.setattr("app.features.teacher_coaching.service.chat", chat_mock)

    await service.detect_and_track_weakness_school(
        AsyncMock(),
        teacher_user_id="teacher-1",
        scores={
            "originality": 3,
            "depth": 9,
            "cultural_relevance": 4,
            "engagement": 4,
            "alignment": 9,
        },
        region="Punjab",
    )

    assert existing.frequency == 2
    assert existing.last_suggestion == "Try grounding in local Punjab examples."  # unchanged
    chat_mock.assert_not_awaited()
    assert _FakeSchoolRepo.created == []


@pytest.mark.asyncio
async def test_response_closes_round_and_next_recurrence_regenerates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Acceptance #3 — repeated ignore -> the AI is asked for a new angle."""
    existing = _memory_row(frequency=2, teacher_response=TeacherResponseType.IGNORED)
    _FakeSchoolRepo.store = {existing.id: existing}
    monkeypatch.setattr(
        "app.features.teacher_coaching.service.SchoolTeacherAiMemoryRepository", _FakeSchoolRepo
    )
    chat_mock = AsyncMock(return_value=_VALID_SUGGESTION_JSON)
    monkeypatch.setattr("app.features.teacher_coaching.service.chat", chat_mock)

    await service.detect_and_track_weakness_school(
        AsyncMock(),
        teacher_user_id="teacher-1",
        scores={
            "originality": 3,
            "depth": 9,
            "cultural_relevance": 4,
            "engagement": 4,
            "alignment": 9,
        },
        region="Punjab",
    )

    chat_mock.assert_awaited_once()
    # The prompt must be told the last suggestion was ignored, so it adapts.
    user_message = chat_mock.call_args.args[0][1]["content"]
    assert "ignored" in user_message
    assert "Try grounding in local Punjab examples." in user_message
    assert existing.frequency == 3
    assert existing.teacher_response == TeacherResponseType.NONE
    assert existing.last_suggestion == "Try opening with a local, everyday example."


@pytest.mark.asyncio
async def test_one_dimension_llm_failure_does_not_block_others(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.features.teacher_coaching.service.SchoolTeacherAiMemoryRepository", _FakeSchoolRepo
    )

    call_count = 0

    async def _flaky_chat(*_a: Any, **_k: Any) -> str:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("LLM provider down")
        return _VALID_SUGGESTION_JSON

    monkeypatch.setattr("app.features.teacher_coaching.service.chat", _flaky_chat)

    await service.detect_and_track_weakness_school(
        AsyncMock(),
        teacher_user_id="teacher-1",
        scores={
            "originality": 3,
            "depth": 3,
            "cultural_relevance": 4,
            "engagement": 4,
            "alignment": 9,
        },
        region=None,
    )

    # originality's LLM call fails (swallowed + logged), depth's succeeds.
    assert len(_FakeSchoolRepo.created) == 1
    assert _FakeSchoolRepo.created[0].weakness_type == "depth"


@pytest.mark.asyncio
async def test_respond_to_suggestion_school_updates_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    existing = _memory_row()
    _FakeSchoolRepo.store = {existing.id: existing}
    monkeypatch.setattr(
        "app.features.teacher_coaching.service.SchoolTeacherAiMemoryRepository", _FakeSchoolRepo
    )

    updated = await service.respond_to_suggestion_school(
        AsyncMock(), teacher_user_id="teacher-1", memory_id=existing.id, response="acted"
    )

    assert updated.teacher_response == TeacherResponseType.ACTED


@pytest.mark.asyncio
async def test_respond_to_suggestion_school_rejects_invalid_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.features.teacher_coaching.service.SchoolTeacherAiMemoryRepository", _FakeSchoolRepo
    )
    with pytest.raises(ValidationError):
        await service.respond_to_suggestion_school(
            AsyncMock(), teacher_user_id="teacher-1", memory_id="nope", response="none"
        )


@pytest.mark.asyncio
async def test_respond_to_suggestion_school_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.features.teacher_coaching.service.SchoolTeacherAiMemoryRepository", _FakeSchoolRepo
    )
    with pytest.raises(NotFoundError):
        await service.respond_to_suggestion_school(
            AsyncMock(), teacher_user_id="teacher-1", memory_id="missing", response="acted"
        )


@pytest.mark.asyncio
async def test_respond_to_suggestion_school_rejects_non_owner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    existing = _memory_row(teacher_user_id="teacher-1")
    _FakeSchoolRepo.store = {existing.id: existing}
    monkeypatch.setattr(
        "app.features.teacher_coaching.service.SchoolTeacherAiMemoryRepository", _FakeSchoolRepo
    )
    with pytest.raises(PermissionDeniedError):
        await service.respond_to_suggestion_school(
            AsyncMock(), teacher_user_id="teacher-2", memory_id=existing.id, response="acted"
        )


@pytest.mark.asyncio
async def test_list_current_suggestions_school_only_pending(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pending = _memory_row(weakness_type="originality", teacher_response=TeacherResponseType.NONE)
    responded = _memory_row(weakness_type="depth", teacher_response=TeacherResponseType.ACTED)
    _FakeSchoolRepo.store = {pending.id: pending, responded.id: responded}
    monkeypatch.setattr(
        "app.features.teacher_coaching.service.SchoolTeacherAiMemoryRepository", _FakeSchoolRepo
    )

    result = await service.list_current_suggestions_school(AsyncMock(), "teacher-1")

    assert [r.weakness_type for r in result] == ["originality"]


@pytest.mark.asyncio
async def test_get_generation_coaching_context_school_returns_suggestion_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pending = _memory_row(last_suggestion="Ground examples locally.")
    _FakeSchoolRepo.store = {pending.id: pending}
    monkeypatch.setattr(
        "app.features.teacher_coaching.service.SchoolTeacherAiMemoryRepository", _FakeSchoolRepo
    )

    context = await service.get_generation_coaching_context_school(
        AsyncMock(), teacher_user_id="teacher-1"
    )

    assert context == ["Ground examples locally."]


# --- resolve_school_teacher_id / resolve_independent_teacher_id -------------

TEACHER = User(
    id="teacher-1",
    authentik_id="auth-teacher",
    email="teacher@example.com",
    display_name="Teacher One",
    role=UserRole.TEACHER,
    status=UserAccountStatus.ACTIVE,
    school_id="school-1",
)
NON_TEACHER = User(
    id="admin-1",
    authentik_id="auth-admin",
    email="admin@example.com",
    display_name="Admin",
    role=UserRole.SCHOOL_ADMIN,
    status=UserAccountStatus.ACTIVE,
    school_id="school-1",
)
IND_TEACHER = IndependentUser(
    id="ind-teacher-1",
    authentik_id="auth-ind-teacher",
    email="ind@example.com",
    display_name="Independent Teacher",
    role=IndependentUserRole.INDEPENDENT_TEACHER,
    status=IndependentUserAccountStatus.ACTIVE,
)


@pytest.mark.asyncio
async def test_resolve_school_teacher_id_success(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FakeUserRepo:
        def __init__(self, _session: Any) -> None:
            pass

        async def get_by_authentik_id(self, authentik_id: str) -> User | None:
            return TEACHER if authentik_id == "auth-teacher" else None

    monkeypatch.setattr("app.features.teacher_coaching.service.UserRepository", _FakeUserRepo)

    teacher_id = await service.resolve_school_teacher_id(AsyncMock(), {"sub": "auth-teacher"})
    assert teacher_id == "teacher-1"


@pytest.mark.asyncio
async def test_resolve_school_teacher_id_rejects_non_teacher(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _FakeUserRepo:
        def __init__(self, _session: Any) -> None:
            pass

        async def get_by_authentik_id(self, authentik_id: str) -> User | None:
            return NON_TEACHER

    monkeypatch.setattr("app.features.teacher_coaching.service.UserRepository", _FakeUserRepo)

    with pytest.raises(PermissionDeniedError):
        await service.resolve_school_teacher_id(AsyncMock(), {"sub": "auth-admin"})


@pytest.mark.asyncio
async def test_resolve_independent_teacher_id_success(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FakeIndUserRepo:
        def __init__(self, _session: Any) -> None:
            pass

        async def get_by_authentik_id(self, authentik_id: str) -> IndependentUser | None:
            return IND_TEACHER if authentik_id == "auth-ind-teacher" else None

    monkeypatch.setattr(
        "app.features.teacher_coaching.service.IndependentUserRepository", _FakeIndUserRepo
    )

    teacher_id = await service.resolve_independent_teacher_id(
        AsyncMock(), {"sub": "auth-ind-teacher"}
    )
    assert teacher_id == "ind-teacher-1"


class _FakeIndependentRepo:
    store: dict[str, IndependentTeacherAiMemory] = {}
    created: list[IndependentTeacherAiMemory] = []

    def __init__(self, _session: Any) -> None:
        pass

    async def get_by_weakness(
        self, *, teacher_user_id: str, category: str, weakness_type: str
    ) -> IndependentTeacherAiMemory | None:
        return next(
            (
                r
                for r in self.store.values()
                if r.teacher_user_id == teacher_user_id
                and r.category == category
                and r.weakness_type == weakness_type
            ),
            None,
        )

    async def create(self, memory: IndependentTeacherAiMemory) -> IndependentTeacherAiMemory:
        self.store[memory.id] = memory
        self.__class__.created.append(memory)
        return memory

    async def update(self, memory: IndependentTeacherAiMemory) -> IndependentTeacherAiMemory:
        return memory


@pytest.mark.asyncio
async def test_detect_and_track_weakness_independent_first_detection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _FakeIndependentRepo.store = {}
    _FakeIndependentRepo.created = []
    monkeypatch.setattr(
        "app.features.teacher_coaching.service.IndependentTeacherAiMemoryRepository",
        _FakeIndependentRepo,
    )
    monkeypatch.setattr(
        "app.features.teacher_coaching.service.chat", AsyncMock(return_value=_VALID_SUGGESTION_JSON)
    )

    await service.detect_and_track_weakness_independent(
        AsyncMock(),
        teacher_user_id="ind-teacher-1",
        scores={
            "originality": 2,
            "depth": 9,
            "cultural_relevance": 4,
            "engagement": 4,
            "alignment": 9,
        },
    )

    assert len(_FakeIndependentRepo.created) == 1
    assert _FakeIndependentRepo.created[0].weakness_type == "originality"
