"""Repository for dual-schema diagnostics — T-103."""

from __future__ import annotations

from datetime import datetime
from typing import cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import ColumnElement

from app.core.tenant import TenantType
from app.db.base import not_deleted
from app.features.diagnostics.models import (
    DiagnosticStatus,
    IndependentDiagnostic,
    SchoolDiagnostic,
)

DiagnosticRow = SchoolDiagnostic | IndependentDiagnostic


class DiagnosticRepository:
    def __init__(self, session: AsyncSession, tenant_type: TenantType) -> None:
        self._session = session
        self._tenant_type = tenant_type
        self._model: type[DiagnosticRow] = (
            IndependentDiagnostic if tenant_type == "independent" else SchoolDiagnostic
        )

    def _scope_clauses(
        self,
        *,
        student_user_id: str,
        subject_id: str | None,
        framework_id: str | None,
    ) -> list[ColumnElement[bool]]:
        clauses: list[ColumnElement[bool]] = [
            self._model.student_user_id == student_user_id,
            not_deleted(self._model),
        ]
        if self._tenant_type == "school":
            clauses.append(self._model.subject_id == subject_id)
        else:
            clauses.append(self._model.framework_id == framework_id)
        return clauses

    async def get_by_id(self, diagnostic_id: str) -> DiagnosticRow | None:
        result = await self._session.execute(
            select(self._model).where(
                self._model.id == diagnostic_id,
                not_deleted(self._model),
            )
        )
        return cast(DiagnosticRow | None, result.scalar_one_or_none())

    async def list_for_scope(
        self,
        *,
        student_user_id: str,
        subject_id: str | None,
        framework_id: str | None,
    ) -> list[DiagnosticRow]:
        result = await self._session.execute(
            select(self._model).where(
                *self._scope_clauses(
                    student_user_id=student_user_id,
                    subject_id=subject_id,
                    framework_id=framework_id,
                )
            )
        )
        return cast(list[DiagnosticRow], list(result.scalars().all()))

    async def list_retake_notify_candidates(
        self, *, cooldown_elapsed_before: datetime
    ) -> list[DiagnosticRow]:
        """Completed diagnostics whose cooldown has elapsed and not yet notified."""
        result = await self._session.execute(
            select(self._model).where(
                self._model.status == DiagnosticStatus.COMPLETED,
                self._model.completed_at.is_not(None),
                self._model.completed_at <= cooldown_elapsed_before,
                self._model.retake_available_notified_at.is_(None),
                not_deleted(self._model),
            )
        )
        return cast(list[DiagnosticRow], list(result.scalars().all()))

    async def create(self, row: DiagnosticRow) -> DiagnosticRow:
        self._session.add(row)
        await self._session.commit()
        await self._session.refresh(row)
        return row

    async def update(self, row: DiagnosticRow) -> DiagnosticRow:
        self._session.add(row)
        await self._session.commit()
        await self._session.refresh(row)
        return row
