"""T-109 — diagnostic notification templates + retake sweep."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock

import pytest

from app.features.diagnostics.events import DIAGNOSTIC_COMPLETED_SUBJECT
from app.features.diagnostics.models import DiagnosticStatus
from app.features.diagnostics.notifications import format_focus_areas_param
from app.features.diagnostics.schemas import FocusAreaRead
from app.features.diagnostics.service import RETAKE_COOLDOWN, DiagnosticService
from app.features.diagnostics.tests.test_diagnostic_lifecycle import _FakeDnaRepo, _FakeRepo
from app.features.student_mode.events import publish_mode_changed
from app.infrastructure.notifications.templates.self_study import (
    TEMPLATE_CHANNELS,
    render_self_study_template,
)

DIAGNOSTIC_TEMPLATE_KEYS = (
    "self_study.diagnostic_available",
    "self_study.diagnostic_completed",
    "self_study.diagnostic_retake_available",
)


@pytest.mark.parametrize("template_key", DIAGNOSTIC_TEMPLATE_KEYS)
def test_diagnostic_templates_all_locales(template_key: str) -> None:
    params = {"focus_areas": "Optics, Friction"} if "completed" in template_key else None
    for locale in ("en", "ur", "sd", "ps"):
        rendered = render_self_study_template(template_key, locale=locale, params=params)
        assert rendered["title"]
        assert rendered["body"]
        assert "__TODO__" not in rendered["title"]
        assert "__TODO__" not in rendered["body"]
        assert "%" not in rendered["body"] or "coaching" in rendered["body"].lower()
    assert template_key in TEMPLATE_CHANNELS


def test_completed_template_is_coaching_not_grade() -> None:
    rendered = render_self_study_template(
        "self_study.diagnostic_completed",
        params={"focus_areas": "Newton's Laws, Optics"},
    )
    body = rendered["body"].lower()
    assert "newton" in body or "optics" in body
    assert "not a grade" in body or "coaching" in body
    assert "score" in body  # "not a grade or score"
    assert "100" not in body


def test_format_focus_areas_param() -> None:
    areas = [
        FocusAreaRead(topic="Optics", suggestion="Spend more time on Optics."),
        FocusAreaRead(topic="Friction", suggestion="Spend more time on Friction."),
    ]
    assert format_focus_areas_param(areas) == "Optics, Friction"


def test_nats_subjects_documented() -> None:
    assert DIAGNOSTIC_COMPLETED_SUBJECT == "student.diagnostic_completed"
    assert publish_mode_changed.__doc__ is not None


@pytest.fixture(autouse=True)
def _patch_diag(monkeypatch: pytest.MonkeyPatch) -> None:
    _FakeRepo.store = {}
    _FakeDnaRepo.store = {}
    monkeypatch.setattr("app.features.diagnostics.service.DiagnosticRepository", _FakeRepo)
    monkeypatch.setattr("app.features.diagnostics.service.CognitiveDnaRepository", _FakeDnaRepo)
    monkeypatch.setattr(
        "app.features.diagnostics.service.publish_diagnostic_completed",
        AsyncMock(),
    )


@pytest.mark.asyncio
async def test_retake_sweep_notifies_after_cooldown(monkeypatch: pytest.MonkeyPatch) -> None:
    notify = AsyncMock()
    monkeypatch.setattr(
        "app.features.diagnostics.notifications.notify_diagnostic_retake_available",
        notify,
    )

    class _User:
        authentik_id = "auth-stu"
        school_id = "school-1"
        deleted_at = None

    class _Profile:
        language_preference = "en"

    class _Users:
        def __init__(self, session: Any) -> None:
            pass

        async def get_by_id(self, user_id: str) -> Any:
            return _User()

    class _Profiles:
        def __init__(self, session: Any) -> None:
            pass

        async def get_by_user_id(self, user_id: str) -> Any:
            return _Profile()

    monkeypatch.setattr("app.features.users.repository.UserRepository", _Users)
    monkeypatch.setattr(
        "app.features.student_onboarding.repository.StudentProfileRepository",
        _Profiles,
    )

    svc = DiagnosticService(session=AsyncMock(), tenant_type="school")
    started = await svc.start(
        student_user_id="stu-1",
        subject_id="subj-1",
        questions=[{"id": "q1", "prompt": "?", "topic": "Optics"}],
    )
    # Bypass _notify_completed during complete
    monkeypatch.setattr(
        "app.features.diagnostics.service.DiagnosticService._notify_completed",
        AsyncMock(),
    )
    await svc.complete(diagnostic_id=started.id)
    row = _FakeRepo.store[started.id]
    row.completed_at = datetime.now(timezone.utc) - RETAKE_COOLDOWN - timedelta(hours=1)
    row.retake_available_notified_at = None
    row.status = DiagnosticStatus.COMPLETED

    count = await svc.send_retake_available_notifications()
    assert count == 1
    notify.assert_awaited_once()
    assert row.retake_available_notified_at is not None

    count2 = await svc.send_retake_available_notifications()
    assert count2 == 0
