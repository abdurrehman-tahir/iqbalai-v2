"""Diagnostic model + lifecycle tests — T-103."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock

import pytest

from app.core.exceptions import PreconditionFailedError, ValidationError
from app.features.diagnostics.models import (
    DiagnosticStatus,
    IndependentDiagnostic,
    SchoolDiagnostic,
)
from app.features.diagnostics.service import (
    RETAKE_BLOCKED_MESSAGE,
    RETAKE_COOLDOWN,
    DiagnosticService,
)


class _FakeRepo:
    store: dict[str, Any] = {}

    def __init__(self, session: Any, tenant_type: str) -> None:
        self.tenant_type = tenant_type

    async def get_by_id(self, diagnostic_id: str) -> Any:
        return self.store.get(diagnostic_id)

    async def list_for_scope(
        self,
        *,
        student_user_id: str,
        subject_id: str | None,
        framework_id: str | None,
    ) -> list[Any]:
        rows = []
        for row in self.store.values():
            if row.student_user_id != student_user_id:
                continue
            if self.tenant_type == "school" and row.subject_id != subject_id:
                continue
            if self.tenant_type == "independent" and row.framework_id != framework_id:
                continue
            rows.append(row)
        return rows

    async def create(self, row: Any) -> Any:
        self.store[row.id] = row
        return row

    async def update(self, row: Any) -> Any:
        self.store[row.id] = row
        return row


@pytest.fixture(autouse=True)
def _patch_repo(monkeypatch: pytest.MonkeyPatch) -> None:
    _FakeRepo.store = {}
    monkeypatch.setattr("app.features.diagnostics.service.DiagnosticRepository", _FakeRepo)


def test_tables_in_separate_schemas() -> None:
    assert SchoolDiagnostic.__table__.schema == "school"
    assert IndependentDiagnostic.__table__.schema == "independent"
    assert SchoolDiagnostic.__tablename__ == "diagnostics"


def test_status_enum_values() -> None:
    assert {s.value for s in DiagnosticStatus} == {
        "not_taken",
        "in_progress",
        "completed",
    }


@pytest.mark.asyncio
async def test_school_start_save_resume_complete() -> None:
    svc = DiagnosticService(session=AsyncMock(), tenant_type="school")
    started = await svc.start(student_user_id="stu-1", subject_id="subj-physics")
    assert started.status == "in_progress"
    assert started.subject_id == "subj-physics"
    assert started.framework_id is None
    assert started.expires_at is not None

    saved = await svc.save_answers(diagnostic_id=started.id, answers={"q1": "A", "q2": "B"})
    assert saved.answers == {"q1": "A", "q2": "B"}

    resumed = await svc.resume(diagnostic_id=started.id)
    assert resumed.answers == {"q1": "A", "q2": "B"}

    done = await svc.complete(diagnostic_id=started.id)
    assert done.status == "completed"
    assert done.completed_at is not None


@pytest.mark.asyncio
async def test_independent_requires_framework_id() -> None:
    svc = DiagnosticService(session=AsyncMock(), tenant_type="independent")
    with pytest.raises(ValidationError):
        await svc.start(student_user_id="ind-1", subject_id="subj-1")
    started = await svc.start(student_user_id="ind-1", framework_id="fw-1")
    assert started.framework_id == "fw-1"
    assert started.tenant_type == "independent"


@pytest.mark.asyncio
async def test_expired_blocks_resume_and_save(monkeypatch: pytest.MonkeyPatch) -> None:
    svc = DiagnosticService(session=AsyncMock(), tenant_type="school")
    started = await svc.start(student_user_id="stu-1", subject_id="subj-1")
    row = _FakeRepo.store[started.id]
    row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)

    with pytest.raises(PreconditionFailedError, match="expired"):
        await svc.resume(diagnostic_id=started.id)
    with pytest.raises(PreconditionFailedError, match="expired"):
        await svc.save_answers(diagnostic_id=started.id, answers={"q1": "A"})


@pytest.mark.asyncio
async def test_retake_cooldown_blocks_early_start() -> None:
    svc = DiagnosticService(session=AsyncMock(), tenant_type="school")
    first = await svc.start(student_user_id="stu-1", subject_id="subj-1")
    await svc.complete(diagnostic_id=first.id)

    with pytest.raises(PreconditionFailedError) as exc:
        await svc.start(student_user_id="stu-1", subject_id="subj-1")
    assert RETAKE_BLOCKED_MESSAGE in str(exc.value)


@pytest.mark.asyncio
async def test_retake_allowed_after_cooldown() -> None:
    svc = DiagnosticService(session=AsyncMock(), tenant_type="school")
    first = await svc.start(student_user_id="stu-1", subject_id="subj-1")
    await svc.complete(diagnostic_id=first.id)
    row = _FakeRepo.store[first.id]
    row.completed_at = datetime.now(timezone.utc) - RETAKE_COOLDOWN - timedelta(hours=1)

    second = await svc.start(student_user_id="stu-1", subject_id="subj-1")
    assert second.id != first.id
    assert second.status == "in_progress"


@pytest.mark.asyncio
async def test_start_returns_existing_active_attempt() -> None:
    svc = DiagnosticService(session=AsyncMock(), tenant_type="school")
    first = await svc.start(student_user_id="stu-1", subject_id="subj-1")
    again = await svc.start(student_user_id="stu-1", subject_id="subj-1")
    assert again.id == first.id
