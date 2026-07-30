"""T-106 — diagnostic completion seeds Cognitive DNA + emits NATS."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest

from app.features.diagnostics.events import DIAGNOSTIC_COMPLETED_SUBJECT
from app.features.diagnostics.service import RETAKE_COOLDOWN, DiagnosticService
from app.features.diagnostics.tests.test_diagnostic_lifecycle import _FakeDnaRepo, _FakeRepo


@pytest.fixture(autouse=True)
def _patch(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    _FakeRepo.store = {}
    _FakeDnaRepo.store = {}
    monkeypatch.setattr("app.features.diagnostics.service.DiagnosticRepository", _FakeRepo)
    monkeypatch.setattr("app.features.diagnostics.service.CognitiveDnaRepository", _FakeDnaRepo)
    publish = AsyncMock()
    monkeypatch.setattr("app.features.diagnostics.service.publish_diagnostic_completed", publish)
    monkeypatch.setattr(
        "app.features.diagnostics.service.DiagnosticService._notify_completed",
        AsyncMock(),
    )
    monkeypatch.setattr("app.features.diagnostics.service.audit", AsyncMock())
    monkeypatch.setattr(
        "app.features.diagnostics.service.DiagnosticService._audit_lifecycle",
        AsyncMock(),
    )
    return publish


@pytest.mark.asyncio
async def test_complete_seeds_school_dna_and_publishes(_patch: AsyncMock) -> None:
    publish = _patch
    svc = DiagnosticService(session=AsyncMock(), tenant_type="school")
    started = await svc.start(
        student_user_id="stu-1",
        subject_id="subj-physics",
        questions=[
            {"id": "q1", "prompt": "Force?", "choices": ["A"], "topic": "Newton's Laws"},
            {"id": "q2", "prompt": "Light?", "choices": ["B"], "topic": "Optics"},
        ],
    )
    await svc.save_answers(diagnostic_id=started.id, answers={"q1": "A"})
    result = await svc.complete(diagnostic_id=started.id)

    key = "stu-1:subj-physics:None"
    assert key in _FakeDnaRepo.store
    dna = _FakeDnaRepo.store[key]
    assert dna["subject_id"] == "subj-physics"
    assert dna["framework_id"] is None
    assert "Newton's Laws" in dna["topic_confidence_jsonb"]
    assert dna["focus_areas_jsonb"]
    assert "%" not in str(dna["topic_confidence_jsonb"])
    assert result.focus_areas

    publish.assert_awaited_once()
    assert publish.await_args is not None
    kwargs = publish.await_args.kwargs
    assert kwargs["diagnostic_id"] == started.id
    assert kwargs["tenant_type"] == "school"
    assert kwargs["subject_id"] == "subj-physics"
    assert kwargs["timed_out"] is False


@pytest.mark.asyncio
async def test_complete_seeds_independent_dna(_patch: AsyncMock) -> None:
    svc = DiagnosticService(session=AsyncMock(), tenant_type="independent")
    started = await svc.start(
        student_user_id="ind-1",
        framework_id="fw-1",
        questions=[{"id": "q1", "prompt": "?", "choices": ["A"], "topic": "Optics"}],
    )
    await svc.complete(diagnostic_id=started.id)
    key = "ind-1:None:fw-1"
    assert key in _FakeDnaRepo.store
    assert _FakeDnaRepo.store[key]["framework_id"] == "fw-1"
    assert _FakeDnaRepo.store[key]["subject_id"] is None
    assert _FakeDnaRepo.store[key]["tenant_type"] == "independent"


@pytest.mark.asyncio
async def test_retake_updates_same_dna_row(_patch: AsyncMock) -> None:
    svc = DiagnosticService(session=AsyncMock(), tenant_type="school")
    first = await svc.start(
        student_user_id="stu-1",
        subject_id="subj-1",
        questions=[{"id": "q1", "prompt": "?", "choices": ["A"], "topic": "Friction"}],
    )
    await svc.complete(diagnostic_id=first.id)
    key = "stu-1:subj-1:None"
    first_id = _FakeDnaRepo.store[key]["id"]

    row = _FakeRepo.store[first.id]
    row.completed_at = datetime.now(timezone.utc) - RETAKE_COOLDOWN - timedelta(hours=1)

    second = await svc.start(
        student_user_id="stu-1",
        subject_id="subj-1",
        questions=[
            {"id": "q1", "prompt": "?", "choices": ["A"], "topic": "Friction"},
            {"id": "q2", "prompt": "?", "choices": ["B"], "topic": "Optics"},
        ],
    )
    await svc.save_answers(diagnostic_id=second.id, answers={"q1": "A", "q2": "B"})
    await svc.complete(diagnostic_id=second.id)

    assert len(_FakeDnaRepo.store) == 1
    assert _FakeDnaRepo.store[key]["id"] == first_id
    assert "Optics" in _FakeDnaRepo.store[key]["topic_confidence_jsonb"]


@pytest.mark.asyncio
async def test_timeout_also_seeds_dna(_patch: AsyncMock) -> None:
    publish = _patch
    svc = DiagnosticService(session=AsyncMock(), tenant_type="school")
    started = await svc.start(
        student_user_id="stu-1",
        subject_id="subj-1",
        questions=[{"id": "q1", "prompt": "?", "topic": "Optics"}],
    )
    row = _FakeRepo.store[started.id]
    row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    await svc.finalize_timeout(diagnostic_id=started.id)
    assert "stu-1:subj-1:None" in _FakeDnaRepo.store
    assert publish.await_args is not None
    assert publish.await_args.kwargs["timed_out"] is True


def test_event_subject_matches_ticket_stream() -> None:
    assert DIAGNOSTIC_COMPLETED_SUBJECT == "student.diagnostic_completed"
