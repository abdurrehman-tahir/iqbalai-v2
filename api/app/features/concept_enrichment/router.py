"""Concept enrichment HTTP API — T-190 (T-191 adds simulation progress)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db, require_role
from app.core.responses import SuccessEnvelope, success
from app.features.concept_enrichment.schemas import (
    ConceptEnrichmentRead,
    LectureConceptRead,
    SimulationProgressRead,
    SimulationStateUpdate,
)
from app.features.concept_enrichment.service import ConceptEnrichmentService
from app.features.concept_enrichment.simulation import SimulationProgressService

router = APIRouter(prefix="/students/me/lectures", tags=["student-concept-enrichment"])

# concept ids may be topic paths containing "/", so they travel as a query param.
_CONCEPT = Query(min_length=1, max_length=128)


@router.get(
    "/{lecture_id}/concepts",
    response_model=SuccessEnvelope[list[LectureConceptRead]],
    operation_id="student_list_lecture_concepts",
    summary="Concepts a lecture covers, each anchored at its first paragraph (T-190)",
    dependencies=[require_role("student")],
)
async def list_lecture_concepts(
    lecture_id: str,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    rows = await ConceptEnrichmentService(db).list_lecture_concepts(claims, lecture_id)
    return success([r.model_dump(mode="json") for r in rows])


@router.get(
    "/{lecture_id}/enrichment",
    response_model=SuccessEnvelope[ConceptEnrichmentRead],
    operation_id="student_get_concept_enrichment",
    summary="Real-world uses, careers and mini-sim for a concept (cached per concept) (T-190)",
    dependencies=[require_role("student")],
)
async def get_concept_enrichment(
    lecture_id: str,
    concept_id: str = _CONCEPT,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    result = await ConceptEnrichmentService(db).get_enrichment(
        claims, lecture_id=lecture_id, concept_id=concept_id
    )
    return success(result.model_dump(mode="json"))


@router.get(
    "/{lecture_id}/simulation",
    response_model=SuccessEnvelope[SimulationProgressRead],
    operation_id="student_get_simulation_progress",
    summary="The student's saved mini-simulation state for a concept (T-191)",
    dependencies=[require_role("student")],
)
async def get_simulation_progress(
    lecture_id: str,
    concept_id: str = _CONCEPT,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    result = await SimulationProgressService(db).get(
        claims, lecture_id=lecture_id, concept_id=concept_id
    )
    return success(result.model_dump(mode="json"))


@router.put(
    "/{lecture_id}/simulation",
    response_model=SuccessEnvelope[SimulationProgressRead],
    operation_id="student_save_simulation_progress",
    summary="Save the student's mini-simulation state for a concept (T-191)",
    dependencies=[require_role("student")],
)
async def save_simulation_progress(
    lecture_id: str,
    payload: SimulationStateUpdate,
    concept_id: str = _CONCEPT,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    result = await SimulationProgressService(db).save(
        claims, lecture_id=lecture_id, concept_id=concept_id, values=payload.values
    )
    return success(result.model_dump(mode="json"))
