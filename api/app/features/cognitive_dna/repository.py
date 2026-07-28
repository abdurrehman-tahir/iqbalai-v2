"""Repository for provisional Cognitive DNA seed rows — T-102 / T-106."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import ColumnElement

from app.core.tenant import TenantType
from app.db.base import not_deleted
from app.features.cognitive_dna.models import (
    CognitiveDnaSource,
    CognitiveDnaTenantType,
    IndependentCognitiveDna,
    SchoolCognitiveDna,
)

CognitiveDnaRow = SchoolCognitiveDna | IndependentCognitiveDna


class CognitiveDnaRepository:
    def __init__(self, session: AsyncSession, tenant_type: TenantType) -> None:
        self._session = session
        self._tenant_type = tenant_type
        self._model: type[CognitiveDnaRow] = (
            IndependentCognitiveDna if tenant_type == "independent" else SchoolCognitiveDna
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

    async def get_by_id(self, dna_id: str) -> CognitiveDnaRow | None:
        result = await self._session.execute(
            select(self._model).where(self._model.id == dna_id, not_deleted(self._model))
        )
        return cast(CognitiveDnaRow | None, result.scalar_one_or_none())

    async def get_for_scope(
        self,
        *,
        student_user_id: str,
        subject_id: str | None,
        framework_id: str | None,
    ) -> CognitiveDnaRow | None:
        result = await self._session.execute(
            select(self._model).where(
                *self._scope_clauses(
                    student_user_id=student_user_id,
                    subject_id=subject_id,
                    framework_id=framework_id,
                )
            )
        )
        return cast(CognitiveDnaRow | None, result.scalar_one_or_none())

    async def list_for_student(self, student_user_id: str) -> list[CognitiveDnaRow]:
        result = await self._session.execute(
            select(self._model).where(
                self._model.student_user_id == student_user_id,
                not_deleted(self._model),
            )
        )
        return cast(list[CognitiveDnaRow], list(result.scalars().all()))

    async def create(self, row: CognitiveDnaRow) -> CognitiveDnaRow:
        self._session.add(row)
        await self._session.commit()
        await self._session.refresh(row)
        return row

    async def upsert_from_diagnostic(
        self,
        *,
        student_user_id: str,
        subject_id: str | None,
        framework_id: str | None,
        topic_confidence_jsonb: dict[str, object],
        focus_areas_jsonb: list[object],
        now: datetime | None = None,
    ) -> CognitiveDnaRow:
        """Create or update the DNA seed for this student+scope (retake updates)."""
        stamp = now or datetime.now(timezone.utc)
        existing = await self.get_for_scope(
            student_user_id=student_user_id,
            subject_id=subject_id,
            framework_id=framework_id,
        )
        if existing is not None:
            existing.topic_confidence_jsonb = topic_confidence_jsonb
            existing.focus_areas_jsonb = focus_areas_jsonb
            existing.source = CognitiveDnaSource.DIAGNOSTIC
            existing.last_updated_at = stamp
            self._session.add(existing)
            await self._session.commit()
            await self._session.refresh(existing)
            return existing

        if self._tenant_type == "independent":
            row: CognitiveDnaRow = IndependentCognitiveDna(
                student_user_id=student_user_id,
                subject_id=None,
                framework_id=framework_id,
                topic_confidence_jsonb=topic_confidence_jsonb,
                focus_areas_jsonb=focus_areas_jsonb,
                source=CognitiveDnaSource.DIAGNOSTIC,
                last_updated_at=stamp,
                tenant_type=CognitiveDnaTenantType.INDEPENDENT,
            )
        else:
            row = SchoolCognitiveDna(
                student_user_id=student_user_id,
                subject_id=subject_id,
                framework_id=None,
                topic_confidence_jsonb=topic_confidence_jsonb,
                focus_areas_jsonb=focus_areas_jsonb,
                source=CognitiveDnaSource.DIAGNOSTIC,
                last_updated_at=stamp,
                tenant_type=CognitiveDnaTenantType.SCHOOL,
            )
        return await self.create(row)
