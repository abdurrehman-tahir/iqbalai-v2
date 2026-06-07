"""Teaching Personas API endpoints — T-021 (Platform Admin only)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db, require_role
from app.core.responses import SuccessEnvelope, success
from app.features.personas.schemas import PersonaRead, PersonaUpdate
from app.features.personas.service import PersonaService

router = APIRouter(prefix="/admin/personas", tags=["personas"])


@router.get(
    "/",
    response_model=SuccessEnvelope[list[PersonaRead]],
    operation_id="list_personas",
    summary="List all teaching personas",
    dependencies=[require_role("platform_admin")],
)
async def list_personas(db: AsyncSession = Depends(get_db)) -> dict:
    svc = PersonaService(db)
    personas = await svc.list_personas()
    return success([PersonaRead.model_validate(p).model_dump() for p in personas])


@router.get(
    "/{persona_id}",
    response_model=SuccessEnvelope[PersonaRead],
    operation_id="get_persona",
    summary="Get a single teaching persona",
    dependencies=[require_role("platform_admin")],
)
async def get_persona(
    persona_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    svc = PersonaService(db)
    persona = await svc.get_persona(persona_id)
    return success(PersonaRead.model_validate(persona).model_dump())


@router.put(
    "/{persona_id}",
    response_model=SuccessEnvelope[PersonaRead],
    operation_id="update_persona",
    summary="Update a teaching persona's prompts or active status",
    dependencies=[require_role("platform_admin")],
)
async def update_persona(
    persona_id: str,
    payload: PersonaUpdate,
    claims: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    svc = PersonaService(db)
    persona = await svc.update_persona(persona_id, payload, updated_by=str(claims.get("sub", "")))
    return success(PersonaRead.model_validate(persona).model_dump())
