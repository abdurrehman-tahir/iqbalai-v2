"""School Admin graduation approval endpoints — T-085."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db, require_role
from app.core.responses import SuccessEnvelope, success
from app.features.graduation.schemas import GraduationRequestRead
from app.features.graduation.service import GraduationService

router = APIRouter(prefix="/school/admin/graduation", tags=["graduation"])


@router.get(
    "/requests",
    response_model=SuccessEnvelope[list[GraduationRequestRead]],
    operation_id="school_admin_list_graduation_requests",
    summary="List graduation requests for the School Admin's school",
    dependencies=[require_role("school_admin")],
)
async def list_graduation_requests(
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = GraduationService(db)
    rows = await svc.list_graduation_requests(claims)
    return success([row.model_dump() for row in rows])


@router.post(
    "/requests/{request_id}/approve",
    response_model=SuccessEnvelope[GraduationRequestRead],
    operation_id="school_admin_approve_graduation",
    summary="Approve a graduation request (enters SCHOOL_READ_ONLY)",
    dependencies=[require_role("school_admin")],
)
async def approve_graduation(
    request_id: str,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = GraduationService(db)
    result = await svc.approve_graduation_request(
        request_id,
        claims,
        actor_id=str(claims.get("sub", "")),
    )
    return success(result.model_dump())
