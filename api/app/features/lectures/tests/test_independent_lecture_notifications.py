"""T-126 — independent-tenant lecture notification helpers."""

from __future__ import annotations

from typing import Any

import pytest

from app.features.lectures import independent_lecture_notifications as notif
from app.features.lectures.models import IndependentLecture, LectureStatus


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


def _lecture(**overrides: Any) -> IndependentLecture:
    fields: dict[str, Any] = {
        "id": "lec-1",
        "teacher_user_id": "teacher-1",
        "title": "Newton's Laws",
        "topic": "Newton's Laws",
        "status": LectureStatus.READY_FOR_EDIT,
    }
    fields.update(overrides)
    return IndependentLecture(**fields)


@pytest.mark.asyncio
async def test_notify_generation_complete_resolves_recipient_and_locale(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _FakeIndependentUserRepo.by_id = {"teacher-1": _FakeIndependentUser("auth-indep", "sd")}
    monkeypatch.setattr(notif, "IndependentUserRepository", _FakeIndependentUserRepo)

    fired: list[dict[str, Any]] = []

    async def _fake_notify(**kwargs: Any) -> None:
        fired.append(kwargs)

    monkeypatch.setattr(notif, "notify_lecture_event", _fake_notify)

    await notif.notify_generation_complete(None, lecture=_lecture())  # type: ignore[arg-type]

    assert fired[0]["recipient_user_id"] == "auth-indep"
    assert fired[0]["locale"] == "sd"
    assert fired[0]["school_id"] is None
    assert fired[0]["template_key"] == "lectures.generation_complete"


@pytest.mark.asyncio
async def test_notify_generation_timeout_school_id_is_none(monkeypatch: pytest.MonkeyPatch) -> None:
    _FakeIndependentUserRepo.by_id = {"teacher-1": _FakeIndependentUser("auth-indep")}
    monkeypatch.setattr(notif, "IndependentUserRepository", _FakeIndependentUserRepo)

    fired: list[dict[str, Any]] = []

    async def _fake_notify(**kwargs: Any) -> None:
        fired.append(kwargs)

    monkeypatch.setattr(notif, "notify_lecture_event", _fake_notify)

    await notif.notify_generation_timeout(None, lecture=_lecture())  # type: ignore[arg-type]

    assert fired[0]["template_key"] == "lectures.generation_timeout"
    assert fired[0]["school_id"] is None


@pytest.mark.asyncio
async def test_notify_helpers_are_best_effort(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Boom:
        def __init__(self, session: Any) -> None:
            pass

        async def get_by_id(self, user_id: str) -> Any:
            raise RuntimeError("db down")

    monkeypatch.setattr(notif, "IndependentUserRepository", _Boom)
    # Must not raise even though recipient resolution blows up.
    await notif.notify_generation_failed(
        None,  # type: ignore[arg-type]
        lecture=_lecture(),
        error="boom",
    )


@pytest.mark.asyncio
async def test_notify_skips_when_user_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    _FakeIndependentUserRepo.by_id = {}
    monkeypatch.setattr(notif, "IndependentUserRepository", _FakeIndependentUserRepo)

    fired: list[dict[str, Any]] = []

    async def _fake_notify(**kwargs: Any) -> None:
        fired.append(kwargs)

    monkeypatch.setattr(notif, "notify_lecture_event", _fake_notify)

    await notif.notify_generation_complete(None, lecture=_lecture())  # type: ignore[arg-type]

    assert fired == []
