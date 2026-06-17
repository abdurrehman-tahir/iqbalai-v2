"""Offering API endpoints — T-045/T-046 (nested under grades)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db, require_role
from app.core.responses import SuccessEnvelope, success
from app.features.offerings.schemas import (
    EligibleTeacherRead,
    OfferingAssign,
    OfferingCreate,
    OfferingRead,
)
from app.features.offerings.service import OfferingService

router = APIRouter(prefix="/grades/{grade_id}/offerings", tags=["offerings"])


@router.get(
    "/",
    response_model=SuccessEnvelope[list[OfferingRead]],
    operation_id="offerings_list",
    summary="List subject offerings for a grade",
    dependencies=[require_role("coordinator")],
)
async def list_offerings(
    grade_id: str,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = OfferingService(db)
    offerings = await svc.list_offerings(grade_id, claims)
    return success([OfferingRead.model_validate(o).model_dump() for o in offerings])


@router.post(
    "/",
    response_model=SuccessEnvelope[OfferingRead],
    operation_id="offerings_create",
    summary="Offer a subject to a grade",
    status_code=201,
    dependencies=[require_role("coordinator")],
)
async def create_offering(
    grade_id: str,
    payload: OfferingCreate,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = OfferingService(db)
    offering = await svc.create_offering(
        grade_id, payload, claims, actor_id=str(claims.get("sub", ""))
    )
    return success(OfferingRead.model_validate(offering).model_dump())


@router.post(
    "/{offering_id}/archive",
    response_model=SuccessEnvelope[OfferingRead],
    operation_id="offerings_archive",
    summary="Archive a grade subject offering",
    dependencies=[require_role("coordinator")],
)
async def archive_offering(
    grade_id: str,
    offering_id: str,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = OfferingService(db)
    offering = await svc.archive_offering(
        grade_id, offering_id, claims, actor_id=str(claims.get("sub", ""))
    )
    return success(OfferingRead.model_validate(offering).model_dump())


@router.get(
    "/eligible-teachers",
    response_model=SuccessEnvelope[list[EligibleTeacherRead]],
    operation_id="offerings_eligible_teachers",
    summary="List teachers eligible for assignment with capacity info",
    dependencies=[require_role("coordinator")],
)
async def list_eligible_teachers(
    grade_id: str,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = OfferingService(db)
    teachers = await svc.list_eligible_teachers(grade_id, claims)
    return success([EligibleTeacherRead.model_validate(t).model_dump() for t in teachers])


@router.post(
    "/{offering_id}/assign",
    response_model=SuccessEnvelope[OfferingRead],
    operation_id="offerings_assign_teacher",
    summary="Assign a teacher to an offering",
    dependencies=[require_role("coordinator")],
)
async def assign_teacher(
    grade_id: str,
    offering_id: str,
    payload: OfferingAssign,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    if_match: str | None = Header(default=None, alias="If-Match"),
) -> dict[str, Any]:
    svc = OfferingService(db)
    offering = await svc.assign_teacher(
        grade_id,
        offering_id,
        payload.teacher_id,
        claims,
        actor_id=str(claims.get("sub", "")),
        override=payload.override,
        if_match=if_match,
    )
    return success(OfferingRead.model_validate(offering).model_dump())


@router.post(
    "/{offering_id}/unassign",
    response_model=SuccessEnvelope[OfferingRead],
    operation_id="offerings_unassign_teacher",
    summary="Unassign the teacher from an offering",
    dependencies=[require_role("coordinator")],
)
async def unassign_teacher(
    grade_id: str,
    offering_id: str,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    if_match: str | None = Header(default=None, alias="If-Match"),
) -> dict[str, Any]:
    svc = OfferingService(db)
    offering = await svc.unassign_teacher(
        grade_id,
        offering_id,
        claims,
        actor_id=str(claims.get("sub", "")),
        if_match=if_match,
    )
    return success(OfferingRead.model_validate(offering).model_dump())
