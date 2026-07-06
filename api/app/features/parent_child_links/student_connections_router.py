"""Student-side parent link connections — T-082."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db, require_role
from app.core.responses import SuccessEnvelope, success
from app.features.parent_child_links.schemas import ParentChildLinkRead, StudentConnectionsRead
from app.features.parent_child_links.service import ParentChildLinkService

router = APIRouter(prefix="/students/me", tags=["student-parent-links"])


@router.get(
    "/connections",
    response_model=SuccessEnvelope[StudentConnectionsRead],
    operation_id="student_get_connections",
    summary="List linked parents and link history for the current student",
    dependencies=[require_role("student")],
)
async def get_student_connections(
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = ParentChildLinkService(db)
    result = await svc.get_student_connections(claims)
    return success(result.model_dump())


@router.post(
    "/links/{link_id}/revoke",
    response_model=SuccessEnvelope[ParentChildLinkRead],
    operation_id="student_revoke_parent_link",
    summary="Revoke an approved parent link",
    dependencies=[require_role("student")],
)
async def revoke_parent_link(
    link_id: str,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = ParentChildLinkService(db)
    result = await svc.revoke_link_as_student(link_id, claims)
    return success(result.model_dump())
