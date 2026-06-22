"""Student-side parent link approval endpoints — T-081."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db, require_role
from app.core.responses import SuccessEnvelope, success
from app.features.parent_child_links.schemas import ParentChildLinkRead, StudentLinkRequestList
from app.features.parent_child_links.service import ParentChildLinkService

router = APIRouter(prefix="/students/me/link-requests", tags=["student-parent-links"])


@router.get(
    "",
    response_model=SuccessEnvelope[StudentLinkRequestList],
    operation_id="student_list_link_requests",
    summary="List pending parent link requests for the current student",
    dependencies=[require_role("student")],
)
async def list_link_requests(
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = ParentChildLinkService(db)
    result = await svc.list_student_pending_requests(claims)
    return success(result.model_dump())


@router.post(
    "/{link_id}/approve",
    response_model=SuccessEnvelope[ParentChildLinkRead],
    operation_id="student_approve_link_request",
    summary="Approve a pending parent link request",
    dependencies=[require_role("student")],
)
async def approve_link_request(
    link_id: str,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = ParentChildLinkService(db)
    result = await svc.approve_link_request(link_id, claims)
    return success(result.model_dump())
