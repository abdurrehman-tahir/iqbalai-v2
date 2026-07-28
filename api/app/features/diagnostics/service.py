"""Diagnostic lifecycle service — T-103 (Flow 4 §3.6).

States: not_taken → in_progress → completed.
Save/resume within 7 days (expires_at). Retake = new attempt after 30-day cooldown.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, cast

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import PreconditionFailedError, ValidationError
from app.core.tenant import TenantType
from app.features.diagnostics.models import (
    DiagnosticStatus,
    DiagnosticTenantType,
    IndependentDiagnostic,
    SchoolDiagnostic,
)
from app.features.diagnostics.repository import DiagnosticRepository, DiagnosticRow
from app.features.diagnostics.schemas import (
    DiagnosticAnswersBlob,
    DiagnosticQuestionsBlob,
    DiagnosticRead,
)

RESUME_WINDOW = timedelta(days=7)
RETAKE_COOLDOWN = timedelta(days=30)
RETAKE_BLOCKED_MESSAGE = (
    "Retake is available 30 days after your last completed diagnostic for this topic"
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class DiagnosticService:
    def __init__(self, session: AsyncSession, tenant_type: TenantType) -> None:
        self._session = session
        self._tenant_type = tenant_type
        self._repo = DiagnosticRepository(session, tenant_type)

    def _validate_scope(self, subject_id: str | None, framework_id: str | None) -> None:
        if self._tenant_type == "school":
            if not subject_id:
                raise ValidationError("School diagnostics require subject_id")
            if framework_id:
                raise ValidationError("School diagnostics must not set framework_id")
        else:
            if not framework_id:
                raise ValidationError("Independent diagnostics require framework_id")
            if subject_id:
                raise ValidationError("Independent diagnostics must not set subject_id")

    def _to_read(self, row: DiagnosticRow) -> DiagnosticRead:
        questions = DiagnosticQuestionsBlob.from_jsonb(row.questions_jsonb)
        answers = DiagnosticAnswersBlob.from_jsonb(row.answers_jsonb)
        return DiagnosticRead(
            id=row.id,
            tenant_type=cast(Any, row.tenant_type.value),
            student_user_id=row.student_user_id,
            subject_id=row.subject_id,
            framework_id=row.framework_id,
            status=cast(Any, row.status.value),
            questions=questions.questions,
            answers=answers.answers,
            started_at=row.started_at,
            completed_at=row.completed_at,
            expires_at=row.expires_at,
        )

    def _is_expired(self, row: DiagnosticRow, now: datetime) -> bool:
        return (
            row.status == DiagnosticStatus.IN_PROGRESS
            and row.expires_at is not None
            and now >= row.expires_at
        )

    async def _latest_completed(
        self,
        *,
        student_user_id: str,
        subject_id: str | None,
        framework_id: str | None,
    ) -> DiagnosticRow | None:
        rows = await self._repo.list_for_scope(
            student_user_id=student_user_id,
            subject_id=subject_id,
            framework_id=framework_id,
        )
        completed = [
            r for r in rows if r.status == DiagnosticStatus.COMPLETED and r.completed_at is not None
        ]
        if not completed:
            return None
        return max(
            completed, key=lambda r: r.completed_at or datetime.min.replace(tzinfo=timezone.utc)
        )

    async def _active_in_progress(
        self,
        *,
        student_user_id: str,
        subject_id: str | None,
        framework_id: str | None,
        now: datetime,
    ) -> DiagnosticRow | None:
        rows = await self._repo.list_for_scope(
            student_user_id=student_user_id,
            subject_id=subject_id,
            framework_id=framework_id,
        )
        for row in rows:
            if row.status == DiagnosticStatus.IN_PROGRESS and not self._is_expired(row, now):
                return row
        return None

    def _assert_cooldown(self, completed: DiagnosticRow | None, now: datetime) -> None:
        if completed is None or completed.completed_at is None:
            return
        if now < completed.completed_at + RETAKE_COOLDOWN:
            raise PreconditionFailedError(RETAKE_BLOCKED_MESSAGE)

    async def start(
        self,
        *,
        student_user_id: str,
        subject_id: str | None = None,
        framework_id: str | None = None,
        questions: list[object] | None = None,
    ) -> DiagnosticRead:
        self._validate_scope(subject_id, framework_id)
        now = _utcnow()

        active = await self._active_in_progress(
            student_user_id=student_user_id,
            subject_id=subject_id,
            framework_id=framework_id,
            now=now,
        )
        if active is not None:
            return self._to_read(active)

        latest = await self._latest_completed(
            student_user_id=student_user_id,
            subject_id=subject_id,
            framework_id=framework_id,
        )
        self._assert_cooldown(latest, now)

        questions_blob = DiagnosticQuestionsBlob.from_jsonb(questions)
        if self._tenant_type == "school":
            row: DiagnosticRow = SchoolDiagnostic(
                student_user_id=student_user_id,
                subject_id=subject_id,
                tenant_type=DiagnosticTenantType.SCHOOL,
                status=DiagnosticStatus.IN_PROGRESS,
                questions_jsonb=questions_blob.to_jsonb(),
                answers_jsonb={},
                started_at=now,
                expires_at=now + RESUME_WINDOW,
            )
        else:
            row = IndependentDiagnostic(
                student_user_id=student_user_id,
                framework_id=framework_id,
                tenant_type=DiagnosticTenantType.INDEPENDENT,
                status=DiagnosticStatus.IN_PROGRESS,
                questions_jsonb=questions_blob.to_jsonb(),
                answers_jsonb={},
                started_at=now,
                expires_at=now + RESUME_WINDOW,
            )
        created = await self._repo.create(row)
        return self._to_read(created)

    async def save_answers(
        self,
        *,
        diagnostic_id: str,
        answers: dict[str, Any],
    ) -> DiagnosticRead:
        row = await self._repo.get_by_id(diagnostic_id)
        if row is None:
            raise PreconditionFailedError("Diagnostic not found or expired")
        now = _utcnow()
        if row.status != DiagnosticStatus.IN_PROGRESS:
            raise PreconditionFailedError("Diagnostic is not in progress")
        if self._is_expired(row, now):
            raise PreconditionFailedError("Diagnostic expired — start a new attempt")

        merged = DiagnosticAnswersBlob.from_jsonb(row.answers_jsonb)
        merged.answers.update(answers)
        row.answers_jsonb = merged.to_jsonb()
        updated = await self._repo.update(row)
        return self._to_read(updated)

    async def resume(self, *, diagnostic_id: str) -> DiagnosticRead:
        row = await self._repo.get_by_id(diagnostic_id)
        if row is None:
            raise PreconditionFailedError("Diagnostic not found or expired")
        now = _utcnow()
        if row.status != DiagnosticStatus.IN_PROGRESS:
            raise PreconditionFailedError("Diagnostic is not in progress")
        if self._is_expired(row, now):
            raise PreconditionFailedError("Diagnostic expired — start a new attempt")
        return self._to_read(row)

    async def complete(self, *, diagnostic_id: str) -> DiagnosticRead:
        row = await self._repo.get_by_id(diagnostic_id)
        if row is None:
            raise PreconditionFailedError("Diagnostic not found or expired")
        now = _utcnow()
        if row.status != DiagnosticStatus.IN_PROGRESS:
            raise PreconditionFailedError("Diagnostic is not in progress")
        if self._is_expired(row, now):
            raise PreconditionFailedError("Diagnostic expired — start a new attempt")

        row.status = DiagnosticStatus.COMPLETED
        row.completed_at = now
        updated = await self._repo.update(row)
        return self._to_read(updated)
