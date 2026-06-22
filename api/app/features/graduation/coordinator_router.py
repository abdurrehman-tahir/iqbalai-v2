"""Graduation coordinator endpoints — T-085."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db, require_role
from app.core.responses import SuccessEnvelope, success
from app.features.graduation.schemas import GraduationRequestCreate, GraduationRequestRead
from app.features.graduation.service import GraduationService

router = APIRouter(prefix="/graduation", tags=["graduation"])


@router.get(
    "/requests",
    response_model=SuccessEnvelope[list[GraduationRequestRead]],
    operation_id="list_graduation_requests",
    summary="List graduation requests for the caller's school",
    dependencies=[require_role("coordinator")],
)
async def list_graduation_requests(
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = GraduationService(db)
    rows = await svc.list_graduation_requests(claims)
    return success([row.model_dump() for row in rows])


@router.post(
    "/requests",
    response_model=SuccessEnvelope[GraduationRequestRead],
    operation_id="create_graduation_request",
    status_code=201,
    summary="Request graduation for a final-grade student",
    dependencies=[require_role("coordinator")],
)
async def create_graduation_request(
    payload: GraduationRequestCreate,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = GraduationService(db)
    result = await svc.create_graduation_request(
        payload.student_user_id,
        claims,
        actor_id=str(claims.get("sub", "")),
    )
    return success(result.model_dump())
