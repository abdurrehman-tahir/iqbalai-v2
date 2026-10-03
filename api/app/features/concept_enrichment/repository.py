"""Persistence for concept enrichment (T-189 / T-190 / T-191)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.concept_enrichment.models import (
    Career,
    ConceptApplicationStatus,
    EnrichmentTenantType,
    SchoolConceptApplication,
    SchoolStudentSimulationProgress,
)


class CareerRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_all(self) -> list[Career]:
        result = await self._session.execute(select(Career).order_by(Career.sector, Career.name))
        return list(result.scalars().all())

    async def get_many(self, ids: list[str]) -> list[Career]:
        if not ids:
            return []
        result = await self._session.execute(select(Career).where(Career.id.in_(ids)))
        by_id = {c.id: c for c in result.scalars().all()}
        return [by_id[i] for i in ids if i in by_id]  # keep the stored order


class ConceptApplicationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_for_concept(
        self, concept_id: str, tenant_type: EnrichmentTenantType
    ) -> SchoolConceptApplication | None:
        result = await self._session.execute(
            select(SchoolConceptApplication).where(
                SchoolConceptApplication.concept_id == concept_id,
                SchoolConceptApplication.tenant_type == tenant_type,
            )
        )
        return result.scalars().first()

    async def get_by_id(self, application_id: str) -> SchoolConceptApplication | None:
        return await self._session.get(SchoolConceptApplication, application_id)

    async def list_due_for_refresh(
        self, *, stale_before: datetime, lost_pending_before: datetime, limit: int
    ) -> list[SchoolConceptApplication]:
        """Rows the daily beat should (re)generate, oldest first:

        - READY rows generated before ``stale_before`` (cache age exceeded);
        - FAILED rows (retry once a day);
        - PENDING rows untouched since ``lost_pending_before`` (lost task).
        """
        result = await self._session.execute(
            select(SchoolConceptApplication)
            .where(
                or_(
                    and_(
                        SchoolConceptApplication.status == ConceptApplicationStatus.READY,
                        SchoolConceptApplication.generated_at < stale_before,
                    ),
                    SchoolConceptApplication.status == ConceptApplicationStatus.FAILED,
                    and_(
                        SchoolConceptApplication.status == ConceptApplicationStatus.PENDING,
                        SchoolConceptApplication.updated_at < lost_pending_before,
                    ),
                )
            )
            .order_by(SchoolConceptApplication.updated_at.asc())
            .limit(limit)
        )
        return list(result.scalars().all())


class SimulationProgressRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_for_student(
        self, *, student_user_id: str, concept_id: str
    ) -> SchoolStudentSimulationProgress | None:
        result = await self._session.execute(
            select(SchoolStudentSimulationProgress).where(
                SchoolStudentSimulationProgress.student_user_id == student_user_id,
                SchoolStudentSimulationProgress.concept_id == concept_id,
            )
        )
        return result.scalars().first()
