"""School Admin (+ inheritance) promotion approval endpoints — T-252 / ARCH §6.21."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db, require_role
from app.core.responses import SuccessEnvelope, success
from app.features.promotions.models import GradePromotionRequestStatus
from app.features.promotions.schemas import (
    GradePromotionRejectBody,
    GradePromotionRequestRead,
)
from app.features.promotions.service import PromotionService

router = APIRouter(prefix="/promotion-requests", tags=["promotions"])


@router.get(
    "",
    response_model=SuccessEnvelope[list[GradePromotionRequestRead]],
    operation_id="promotion_requests_list",
    summary="List promotion requests for the caller's school",
    dependencies=[require_role("school_admin")],
)
async def list_promotion_requests(
    status: GradePromotionRequestStatus | None = Query(default=None),
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = PromotionService(db)
    rows = await svc.list_promotion_requests(
        claims,
        actor_id=str(claims.get("sub", "")),
        status=status,
    )
    return success([row.model_dump() for row in rows])


@router.get(
    "/{request_id}",
    response_model=SuccessEnvelope[GradePromotionRequestRead],
    operation_id="promotion_requests_get",
    summary="View a promotion request (coordinator+ scoped)",
    dependencies=[require_role("coordinator")],
)
async def get_promotion_request(
    request_id: str,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = PromotionService(db)
    result = await svc.get_promotion_request(
        request_id, claims, actor_id=str(claims.get("sub", ""))
    )
    return success(result.model_dump())


@router.post(
    "/{request_id}/approve",
    response_model=SuccessEnvelope[GradePromotionRequestRead],
    operation_id="promotion_requests_approve",
    summary="Approve a pending promotion request",
    dependencies=[require_role("school_admin")],
)
async def approve_promotion_request(
    request_id: str,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = PromotionService(db)
    result = await svc.approve_promotion_request(
        request_id, claims, actor_id=str(claims.get("sub", ""))
    )
    return success(result.model_dump())


@router.post(
    "/{request_id}/reject",
    response_model=SuccessEnvelope[GradePromotionRequestRead],
    operation_id="promotion_requests_reject",
    summary="Reject a pending promotion request",
    dependencies=[require_role("school_admin")],
)
async def reject_promotion_request(
    request_id: str,
    payload: GradePromotionRejectBody | None = None,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = PromotionService(db)
    reason = payload.reason if payload is not None else None
    result = await svc.reject_promotion_request(
        request_id, claims, actor_id=str(claims.get("sub", "")), reason=reason
    )
    return success(result.model_dump())
