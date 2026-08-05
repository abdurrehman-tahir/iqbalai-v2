"""T-126 — lecture generation notifications: templates, dispatcher, school helpers."""

from __future__ import annotations

from typing import Any

import pytest

from app.features.lectures import lecture_notifications as notif
from app.features.lectures.models import LectureStatus, LectureType, SchoolLecture
from app.infrastructure.notifications.templates.lectures import (
    LECTURE_TEMPLATES,
    SUPPORTED_LOCALES,
    render_lecture_template,
)

# --- templates (Acceptance #4) ----------------------------------------------


def test_every_template_has_all_four_locales_without_todo() -> None:
    assert SUPPORTED_LOCALES == frozenset({"en", "ur", "sd", "ps"})
    for template_key, variants in LECTURE_TEMPLATES.items():
        for locale in SUPPORTED_LOCALES:
            fields = variants["default"][locale]
            assert fields["title"] and fields["body"], f"{template_key}/{locale} empty"
            assert "__TODO__" not in fields["title"]
            assert "__TODO__" not in fields["body"]


def test_render_fills_topic_placeholder() -> None:
    rendered = render_lecture_template(
        "lectures.generation_complete", locale="en", params={"topic": "Newton's Laws"}
    )
    assert "Newton's Laws" in rendered["body"]


def test_render_falls_back_to_default_locale() -> None:
    rendered = render_lecture_template(
        "lectures.generation_failed", locale="fr", params={"topic": "X"}
    )
    assert (
        rendered["title"]
        == LECTURE_TEMPLATES["lectures.generation_failed"]["default"]["en"]["title"]
    )


# --- dispatcher (Acceptance #1) ----------------------------------------------


@pytest.mark.asyncio
async def test_dispatcher_publishes_under_lectures_namespace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.infrastructure.notifications import lectures as dispatcher

    calls: list[dict[str, Any]] = []

    async def _fake_publish(**kwargs: Any) -> None:
        calls.append(kwargs)

    monkeypatch.setattr(dispatcher, "publish_notification", _fake_publish)

    await dispatcher.notify_lecture_event(
        session=None,  # type: ignore[arg-type]
        template_key="lectures.generation_complete",
        recipient_user_id="auth-teacher",
        school_id="school-1",
        params={"topic": "Forces"},
    )

    assert calls[0]["feature_namespace"] == "lectures"
    assert calls[0]["recipient_user_id"] == "auth-teacher"
    assert calls[0]["school_id"] == "school-1"


@pytest.mark.asyncio
async def test_dispatcher_rejects_unknown_template() -> None:
    from app.infrastructure.notifications import lectures as dispatcher

    with pytest.raises(ValueError, match="No channel mapping"):
        await dispatcher.notify_lecture_event(
            session=None,  # type: ignore[arg-type]
            template_key="lectures.not_a_real_key",
            recipient_user_id="auth-teacher",
        )


# --- school helpers (recipient resolution + best-effort) --------------------


class _FakeUser:
    def __init__(self, authentik_id: str) -> None:
        self.authentik_id = authentik_id


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


def _lecture(**overrides: Any) -> SchoolLecture:
    fields: dict[str, Any] = {
        "id": "lec-1",
        "school_id": "school-1",
        "teacher_user_id": "teacher-1",
        "title": "Forces",
        "topic": "Forces",
        "lecture_type": LectureType.MAIN,
        "status": LectureStatus.READY_FOR_EDIT,
    }
    fields.update(overrides)
    return SchoolLecture(**fields)


@pytest.mark.asyncio
async def test_notify_generation_complete_resolves_recipient_and_locale(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _FakeUserRepo.by_id = {"teacher-1": _FakeUser("auth-teacher")}
    _FakeProfileRepo.by_user_id = {"teacher-1": _FakeProfile("ur")}
    monkeypatch.setattr(notif, "UserRepository", _FakeUserRepo)
    monkeypatch.setattr(notif, "TeacherProfileRepository", _FakeProfileRepo)

    fired: list[dict[str, Any]] = []

    async def _fake_notify(**kwargs: Any) -> None:
        fired.append(kwargs)

    monkeypatch.setattr(notif, "notify_lecture_event", _fake_notify)

    await notif.notify_generation_complete(None, lecture=_lecture())  # type: ignore[arg-type]

    assert fired[0]["recipient_user_id"] == "auth-teacher"
    assert fired[0]["locale"] == "ur"
    assert fired[0]["template_key"] == "lectures.generation_complete"
    assert fired[0]["school_id"] == "school-1"


@pytest.mark.asyncio
async def test_notify_generation_failed_includes_error_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _FakeUserRepo.by_id = {"teacher-1": _FakeUser("auth-teacher")}
    _FakeProfileRepo.by_user_id = {}
    monkeypatch.setattr(notif, "UserRepository", _FakeUserRepo)
    monkeypatch.setattr(notif, "TeacherProfileRepository", _FakeProfileRepo)

    fired: list[dict[str, Any]] = []

    async def _fake_notify(**kwargs: Any) -> None:
        fired.append(kwargs)

    monkeypatch.setattr(notif, "notify_lecture_event", _fake_notify)

    await notif.notify_generation_failed(
        None,  # type: ignore[arg-type]
        lecture=_lecture(),
        error="LLM provider down",
    )

    assert fired[0]["template_key"] == "lectures.generation_failed"
    assert fired[0]["metadata"]["error"] == "LLM provider down"
    # No profile row found -> default locale, not a crash.
    assert fired[0]["locale"] == "en"


@pytest.mark.asyncio
async def test_notify_helpers_are_best_effort(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Boom:
        def __init__(self, session: Any) -> None:
            pass

        async def get_by_id(self, user_id: str) -> Any:
            raise RuntimeError("db down")

    monkeypatch.setattr(notif, "UserRepository", _Boom)
    # Must not raise even though recipient resolution blows up.
    await notif.notify_generation_timeout(None, lecture=_lecture())  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_notify_skips_when_teacher_has_no_id(monkeypatch: pytest.MonkeyPatch) -> None:
    fired: list[dict[str, Any]] = []

    async def _fake_notify(**kwargs: Any) -> None:
        fired.append(kwargs)

    monkeypatch.setattr(notif, "notify_lecture_event", _fake_notify)

    await notif.notify_generation_complete(
        None,  # type: ignore[arg-type]
        lecture=_lecture(teacher_user_id=None),
    )

    assert fired == []
