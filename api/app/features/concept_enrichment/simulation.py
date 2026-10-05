"""Per-student mini-simulation state — T-191 (flow-6 §3.10 / §5.9, #71).

State is stored per (student, concept) in ``student_simulation_progress`` as
``{"values": {<variable key>: <number>}}``. Every write is validated against
the concept's *current* sim spec (declared keys only, within min/max), so a
student can never persist arbitrary JSON. If stored state stops matching the
spec (e.g. the concept was re-enriched with different variables), it is
discarded and the student sees "your progress was reset" (§5.9).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.features.concept_enrichment.models import (
    ConceptApplicationStatus,
    EnrichmentTenantType,
    SchoolStudentSimulationProgress,
)
from app.features.concept_enrichment.repository import (
    ConceptApplicationRepository,
    SimulationProgressRepository,
)
from app.features.concept_enrichment.schemas import MiniSimSpecRead, SimulationProgressRead
from app.features.concept_enrichment.service import ConceptEnrichmentService


def _state_matches(values: Any, spec: MiniSimSpecRead) -> bool:  # noqa: ANN401
    if not isinstance(values, dict):
        return False
    bounds = {v.key: (v.min, v.max) for v in spec.variables}
    if set(values) - set(bounds):
        return False
    for key, raw in values.items():
        if not isinstance(raw, (int, float)) or isinstance(raw, bool):
            return False
        lo, hi = bounds[key]
        if not lo <= float(raw) <= hi:
            return False
    return True


class SimulationProgressService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._enrichment = ConceptEnrichmentService(session)
        self._applications = ConceptApplicationRepository(session)
        self._progress = SimulationProgressRepository(session)

    async def _spec(self, concept_id: str) -> MiniSimSpecRead:
        row = await self._applications.get_for_concept(concept_id, EnrichmentTenantType.SCHOOL)
        if row is None or row.status != ConceptApplicationStatus.READY or not row.mini_sim_prompt:
            raise NotFoundError("This concept has no mini-simulation")
        return MiniSimSpecRead.model_validate(row.mini_sim_prompt)

    async def get(
        self, claims: dict[str, object], *, lecture_id: str, concept_id: str
    ) -> SimulationProgressRead:
        student, _ = await self._enrichment.require_lecture_concept(
            claims, lecture_id=lecture_id, concept_id=concept_id
        )
        spec = await self._spec(concept_id)
        row = await self._progress.get_for_student(
            student_user_id=student.id, concept_id=concept_id
        )
        if row is None:
            return SimulationProgressRead(concept_id=concept_id)
        values = row.sim_state.get("values") if isinstance(row.sim_state, dict) else None
        if not _state_matches(values, spec):
            # Corrupted / out-of-date state: reset rather than error (§5.9).
            row.sim_state = {}
            await self._session.commit()
            return SimulationProgressRead(concept_id=concept_id, was_reset=True)
        assert isinstance(values, dict)
        return SimulationProgressRead(
            concept_id=concept_id,
            values={k: float(v) for k, v in values.items()},
            updated_at=row.updated_at,
        )

    async def save(
        self,
        claims: dict[str, object],
        *,
        lecture_id: str,
        concept_id: str,
        values: dict[str, float],
    ) -> SimulationProgressRead:
        student, _ = await self._enrichment.require_lecture_concept(
            claims, lecture_id=lecture_id, concept_id=concept_id
        )
        spec = await self._spec(concept_id)
        if not _state_matches(values, spec):
            raise ValidationError("Simulation values do not match this concept's simulation")
        row = await self._progress.get_for_student(
            student_user_id=student.id, concept_id=concept_id
        )
        if row is None:
            row = SchoolStudentSimulationProgress(
                student_user_id=student.id,
                concept_id=concept_id,
                sim_state={"values": values},
            )
            try:
                async with self._session.begin_nested():
                    self._session.add(row)
                    await self._session.flush()
            except IntegrityError:
                # Two tabs saved at once — update the row the other one created.
                existing = await self._progress.get_for_student(
                    student_user_id=student.id, concept_id=concept_id
                )
                if existing is None:
                    raise
                row = existing
                row.sim_state = {"values": values}
        else:
            row.sim_state = {"values": values}
        await self._session.commit()
        return SimulationProgressRead(
            concept_id=concept_id, values=dict(values), updated_at=row.updated_at
        )
