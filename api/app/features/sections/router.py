"""Section API endpoints — T-044 (nested under grades)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db, require_role
from app.core.responses import SuccessEnvelope, success
from app.features.sections.schemas import SectionCreate, SectionRead
from app.features.sections.service import SectionService

router = APIRouter(prefix="/grades/{grade_id}/sections", tags=["sections"])


@router.get(
    "/",
    response_model=SuccessEnvelope[list[SectionRead]],
    operation_id="sections_list",
    summary="List visible sections for a grade",
    dependencies=[require_role("coordinator")],
)
async def list_sections(
    grade_id: str,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = SectionService(db)
    sections = await svc.list_sections(grade_id, claims)
    return success([SectionRead.model_validate(s).model_dump() for s in sections])


@router.post(
    "/",
    response_model=SuccessEnvelope[SectionRead],
    operation_id="sections_create",
    summary="Add a section to a grade",
    status_code=201,
    dependencies=[require_role("coordinator")],
)
async def create_section(
    grade_id: str,
    payload: SectionCreate,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = SectionService(db)
    section = await svc.create_section(
        grade_id, payload, claims, actor_id=str(claims.get("sub", ""))
    )
    return success(SectionRead.model_validate(section).model_dump())


@router.post(
    "/{section_id}/archive",
    response_model=SuccessEnvelope[SectionRead],
    operation_id="sections_archive",
    summary="Archive a section",
    dependencies=[require_role("coordinator")],
)
async def archive_section(
    grade_id: str,
    section_id: str,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = SectionService(db)
    section = await svc.archive_section(
        grade_id, section_id, claims, actor_id=str(claims.get("sub", ""))
    )
    return success(SectionRead.model_validate(section).model_dump())
