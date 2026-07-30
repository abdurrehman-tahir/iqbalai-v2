"""Audit-registration tests — T-110 (ARCH §14.10 / M-08)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from app.features.audit.actions import (
    COGNITIVE_DNA_SEEDED,
    DIAGNOSTIC_COMPLETED,
    DIAGNOSTIC_RETAKEN,
    DIAGNOSTIC_STARTED,
    ELEVATED_AUDIT_ACTIONS,
    M08_AUDIT_ACTIONS,
    REGISTERED_AUDIT_ACTIONS,
    STUDENT_MODE_CHANGED,
)
from app.features.diagnostics.service import RETAKE_COOLDOWN, DiagnosticService
from app.features.diagnostics.tests.test_diagnostic_lifecycle import _FakeDnaRepo, _FakeRepo

_EMITTED_BY_DIAGNOSTICS = {
    DIAGNOSTIC_STARTED,
    DIAGNOSTIC_COMPLETED,
    DIAGNOSTIC_RETAKEN,
    COGNITIVE_DNA_SEEDED,
}


class _Users:
    def __init__(self, session: Any) -> None:
        pass

    async def get_by_id(self, user_id: str) -> Any:
        return type("U", (), {"school_id": "school-1"})()


def test_m08_actions_registered() -> None:
    assert M08_AUDIT_ACTIONS <= REGISTERED_AUDIT_ACTIONS
    assert STUDENT_MODE_CHANGED in M08_AUDIT_ACTIONS
    assert _EMITTED_BY_DIAGNOSTICS <= M08_AUDIT_ACTIONS


def test_mode_and_diagnostic_not_elevated() -> None:
    for action in M08_AUDIT_ACTIONS:
        assert action not in ELEVATED_AUDIT_ACTIONS


@pytest.fixture(autouse=True)
def _patch(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    _FakeRepo.store = {}
    _FakeDnaRepo.store = {}
    monkeypatch.setattr("app.features.diagnostics.service.DiagnosticRepository", _FakeRepo)
    monkeypatch.setattr("app.features.diagnostics.service.CognitiveDnaRepository", _FakeDnaRepo)
    monkeypatch.setattr(
        "app.features.diagnostics.service.publish_diagnostic_completed",
        AsyncMock(),
    )
    monkeypatch.setattr(
        "app.features.diagnostics.service.DiagnosticService._notify_completed",
        AsyncMock(),
    )
    audit_mock = AsyncMock()
    monkeypatch.setattr("app.features.diagnostics.service.audit", audit_mock)
    return audit_mock


@pytest.mark.asyncio
async def test_start_and_complete_emit_audit(_patch: AsyncMock) -> None:
    audit_mock = _patch
    with patch("app.features.users.repository.UserRepository", _Users):
        svc = DiagnosticService(session=AsyncMock(), tenant_type="school")
        started = await svc.start(
            student_user_id="stu-1",
            subject_id="subj-1",
            questions=[{"id": "q1", "prompt": "?", "topic": "Optics"}],
        )
        await svc.complete(diagnostic_id=started.id)

    actions = [c.kwargs["action"] for c in audit_mock.await_args_list]
    assert DIAGNOSTIC_STARTED in actions
    assert DIAGNOSTIC_COMPLETED in actions
    assert COGNITIVE_DNA_SEEDED in actions
    assert all(c.kwargs.get("school_id") == "school-1" for c in audit_mock.await_args_list)


@pytest.mark.asyncio
async def test_retake_emits_diagnostic_retaken(_patch: AsyncMock) -> None:
    audit_mock = _patch
    with patch("app.features.users.repository.UserRepository", _Users):
        svc = DiagnosticService(session=AsyncMock(), tenant_type="school")
        first = await svc.start(
            student_user_id="stu-1",
            subject_id="subj-1",
            questions=[{"id": "q1", "prompt": "?", "topic": "Optics"}],
        )
        await svc.complete(diagnostic_id=first.id)
        row = _FakeRepo.store[first.id]
        row.completed_at = datetime.now(timezone.utc) - RETAKE_COOLDOWN - timedelta(hours=1)
        audit_mock.reset_mock()
        second = await svc.start(
            student_user_id="stu-1",
            subject_id="subj-1",
            questions=[{"id": "q1", "prompt": "?", "topic": "Optics"}],
        )

    assert second.id != first.id
    actions = [c.kwargs["action"] for c in audit_mock.await_args_list]
    assert DIAGNOSTIC_RETAKEN in actions
    assert DIAGNOSTIC_STARTED not in actions
