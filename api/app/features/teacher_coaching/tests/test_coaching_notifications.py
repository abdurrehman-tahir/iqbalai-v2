"""T-140 — Teaching Innovation Record notification wiring (Flow 5 §3.10 #36).

Covers: (1) the notify helpers resolve recipient/locale and fire under the
``lectures`` namespace with no score/number in the body; (2) the weakness
detectors call notify exactly once per run on a NEW suggestion, and never
when a recurrence just bumps frequency silently.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock

import pytest

from app.features.teacher_coaching import service
from app.features.teacher_coaching.models import SchoolTeacherAiMemory, TeacherResponseType

_VALID_SUGGESTION_JSON = '{"suggestion": "Try opening with a local, everyday example."}'


class _FakeSchoolMemoryRepo:
    store: dict[str, SchoolTeacherAiMemory] = {}
    created: list[SchoolTeacherAiMemory] = []
    updated: list[SchoolTeacherAiMemory] = []

    def __init__(self, _session: Any) -> None:
        pass

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


@pytest.fixture(autouse=True)
def _reset_fake_repo() -> None:
    _FakeSchoolMemoryRepo.store = {}
    _FakeSchoolMemoryRepo.created = []
    _FakeSchoolMemoryRepo.updated = []


class _FakeUser:
    def __init__(self, authentik_id: str, school_id: str | None = "school-1") -> None:
        self.authentik_id = authentik_id
        self.school_id = school_id


class _FakeUserRepo:
    by_id: dict[str, _FakeUser] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def get_by_id(self, user_id: str) -> _FakeUser | None:
        return self.by_id.get(user_id)


class _FakeProfile:
    def __init__(self, language_preference: str) -> None:
        self.language_preference = language_preference


class _FakeProfileRepo:
    by_user_id: dict[str, _FakeProfile] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def get_by_user_id(self, user_id: str) -> _FakeProfile | None:
        return self.by_user_id.get(user_id)


class _FakeIndependentUser:
    def __init__(self, authentik_id: str, language_preference: str = "en") -> None:
        self.authentik_id = authentik_id
        self.language_preference = language_preference


class _FakeIndependentUserRepo:
    by_id: dict[str, _FakeIndependentUser] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def get_by_id(self, user_id: str) -> _FakeIndependentUser | None:
        return self.by_id.get(user_id)


@pytest.mark.asyncio
async def test_notify_coaching_suggestion_school_resolves_recipient_and_locale(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _FakeUserRepo.by_id = {"teacher-1": _FakeUser("auth-teacher")}
    _FakeProfileRepo.by_user_id = {"teacher-1": _FakeProfile("ur")}
    monkeypatch.setattr(service, "UserRepository", _FakeUserRepo)
    monkeypatch.setattr(service, "TeacherProfileRepository", _FakeProfileRepo)

    fired: list[dict[str, Any]] = []

    async def _fake_notify(**kwargs: Any) -> None:
        fired.append(kwargs)

    monkeypatch.setattr(service, "notify_lecture_event", _fake_notify)

    await service._notify_coaching_suggestion_school(None, "teacher-1")  # type: ignore[arg-type]

    assert fired[0]["template_key"] == "lectures.coaching_suggestion"
    assert fired[0]["recipient_user_id"] == "auth-teacher"
    assert fired[0]["locale"] == "ur"
    assert fired[0]["school_id"] == "school-1"
    # Coaching framing only — no score/number anywhere in the fired params.
    assert "params" not in fired[0] or not fired[0].get("params")


@pytest.mark.asyncio
async def test_notify_coaching_suggestion_school_is_best_effort(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _Boom:
        def __init__(self, session: Any) -> None:
            pass

        async def get_by_id(self, user_id: str) -> Any:
            raise RuntimeError("db down")

    monkeypatch.setattr(service, "UserRepository", _Boom)
    await service._notify_coaching_suggestion_school(None, "teacher-1")  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_notify_coaching_suggestion_independent_resolves_recipient_and_locale(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _FakeIndependentUserRepo.by_id = {"teacher-1": _FakeIndependentUser("auth-indep", "sd")}
    monkeypatch.setattr(service, "IndependentUserRepository", _FakeIndependentUserRepo)

    fired: list[dict[str, Any]] = []

    async def _fake_notify(**kwargs: Any) -> None:
        fired.append(kwargs)

    monkeypatch.setattr(service, "notify_lecture_event", _fake_notify)

    await service._notify_coaching_suggestion_independent(
        None,
        "teacher-1",  # type: ignore[arg-type]
    )

    assert fired[0]["template_key"] == "lectures.coaching_suggestion"
    assert fired[0]["locale"] == "sd"
    assert fired[0]["school_id"] is None


@pytest.mark.asyncio
async def test_detect_and_track_weakness_school_notifies_once_on_new_suggestion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.features.teacher_coaching.service.SchoolTeacherAiMemoryRepository",
        _FakeSchoolMemoryRepo,
    )
    monkeypatch.setattr(
        "app.features.teacher_coaching.service.chat", AsyncMock(return_value=_VALID_SUGGESTION_JSON)
    )
    notify_mock = AsyncMock()
    monkeypatch.setattr(service, "_notify_coaching_suggestion_school", notify_mock)

    await service.detect_and_track_weakness_school(
        None,  # type: ignore[arg-type]
        teacher_user_id="teacher-1",
        scores={"originality": 3, "depth": 9, "cultural_relevance": 4, "engagement": 4},
        region="Punjab",
    )

    notify_mock.assert_awaited_once_with(None, "teacher-1")


@pytest.mark.asyncio
async def test_detect_and_track_weakness_school_no_notify_on_silent_bump(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pending = SchoolTeacherAiMemory(
        teacher_user_id="teacher-1",
        category="quality_dimension",
        weakness_type="originality",
        frequency=1,
        last_suggestion="Try grounding in local Punjab examples.",
        teacher_response=TeacherResponseType.NONE,
    )
    pending.updated_at = datetime.now(timezone.utc)
    _FakeSchoolMemoryRepo.store = {pending.id: pending}
    monkeypatch.setattr(
        "app.features.teacher_coaching.service.SchoolTeacherAiMemoryRepository",
        _FakeSchoolMemoryRepo,
    )
    notify_mock = AsyncMock()
    monkeypatch.setattr(service, "_notify_coaching_suggestion_school", notify_mock)

    await service.detect_and_track_weakness_school(
        None,  # type: ignore[arg-type]
        teacher_user_id="teacher-1",
        scores={"originality": 3},
        region="Punjab",
    )

    notify_mock.assert_not_awaited()
