"""Promotion initiate + roster endpoints — T-251."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db, require_role
from app.core.responses import SuccessEnvelope, success
from app.features.promotions.schemas import (
    GradePromotionRequestCreate,
    GradePromotionRequestRead,
    PromotionRosterStudentRead,
)
from app.features.promotions.service import PromotionService

router = APIRouter(
    prefix="/grades/{grade_id}/promotion-requests",
    tags=["promotions"],
)


@router.get(
    "/roster",
    response_model=SuccessEnvelope[list[PromotionRosterStudentRead]],
    operation_id="promotion_requests_roster",
    summary="List active grade roster for promotion exclusion checkboxes",
    dependencies=[require_role("coordinator")],
)
async def list_promotion_roster(
    grade_id: str,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = PromotionService(db)
    rows = await svc.list_roster_for_promotion(
        grade_id, claims, actor_id=str(claims.get("sub", ""))
    )
    return success([row.model_dump() for row in rows])


@router.post(
    "/",
    response_model=SuccessEnvelope[GradePromotionRequestRead],
    operation_id="promotion_requests_create",
    status_code=201,
    summary="Initiate a grade promotion request with exclusion list",
    dependencies=[require_role("coordinator")],
)
async def create_promotion_request(
    grade_id: str,
    payload: GradePromotionRequestCreate,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = PromotionService(db)
    result = await svc.create_promotion_request(
        grade_id,
        payload,
        claims,
        actor_id=str(claims.get("sub", "")),
    )
    return success(result.model_dump())
