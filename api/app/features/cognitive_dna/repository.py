"""Repository for provisional Cognitive DNA seed rows — T-102."""

from __future__ import annotations

from typing import cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tenant import TenantType
from app.db.base import not_deleted
from app.features.cognitive_dna.models import IndependentCognitiveDna, SchoolCognitiveDna

CognitiveDnaRow = SchoolCognitiveDna | IndependentCognitiveDna


class CognitiveDnaRepository:
    def __init__(self, session: AsyncSession, tenant_type: TenantType) -> None:
        self._session = session
        self._tenant_type = tenant_type
        self._model: type[CognitiveDnaRow] = (
            IndependentCognitiveDna if tenant_type == "independent" else SchoolCognitiveDna
        )

    async def get_by_id(self, dna_id: str) -> CognitiveDnaRow | None:
        result = await self._session.execute(
            select(self._model).where(self._model.id == dna_id, not_deleted(self._model))
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
