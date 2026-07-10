"""School API endpoints — T-031 (District Admin + Platform Admin inheritance)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db, require_role
from app.core.idempotency import IdempotencyContext, idempotency_key
from app.core.responses import success
from app.features.schools.schemas import SchoolCreate, SchoolRead, SchoolUpdate
from app.features.schools.service import SchoolService

router = APIRouter(prefix="/admin/schools", tags=["schools"])


def _caller_role(claims: dict[str, object]) -> str:
    return str(claims.get("role", ""))


@router.get(
    "/",
    response_model=dict,
    summary="List schools (scoped to caller's district)",
    operation_id="schools_list",
    dependencies=[require_role("district_admin")],
)
async def list_schools(
    claims: dict[str, object] = Depends(get_current_user),
    district_id: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = SchoolService(db)
    schools = await svc.list_schools(claims, _caller_role(claims), district_id=district_id)
    return success([SchoolRead.model_validate(s).model_dump() for s in schools])


@router.post(
    "/",
    response_model=dict,
    summary="Create a school within a district",
    operation_id="schools_create",
    status_code=201,
    dependencies=[require_role("district_admin")],
)
async def create_school(
    payload: SchoolCreate,
    claims: dict[str, object] = Depends(get_current_user),
    idem: IdempotencyContext | None = Depends(idempotency_key),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    if idem is not None:
        cached = await idem.cached_response()
        if cached is not None:
            return cached

    svc = SchoolService(db)
    school = await svc.create_school(
        payload,
        actor_id=str(claims.get("sub", "")),
        claims=claims,
        caller_role=_caller_role(claims),
    )
    response = success(SchoolRead.model_validate(school).model_dump(mode="json"))

    if idem is not None:
        await idem.store_response(response)
    return response


@router.get(
    "/{school_id}",
    response_model=dict,
    summary="Get a single school",
    operation_id="schools_get",
    dependencies=[require_role("district_admin")],
)
async def get_school(
    school_id: str,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = SchoolService(db)
    school = await svc.get_school(school_id, claims, _caller_role(claims))
    return success(SchoolRead.model_validate(school).model_dump())


@router.put(
    "/{school_id}",
    response_model=dict,
    summary="Update a school",
    operation_id="schools_update",
    dependencies=[require_role("district_admin")],
)
async def update_school(
    school_id: str,
    payload: SchoolUpdate,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = SchoolService(db)
    school = await svc.update_school(
        school_id,
        payload,
        actor_id=str(claims.get("sub", "")),
        claims=claims,
        caller_role=_caller_role(claims),
    )
    return success(SchoolRead.model_validate(school).model_dump())


@router.delete(
    "/{school_id}",
    response_model=dict,
    summary="Soft-delete a school",
    operation_id="schools_delete",
    dependencies=[require_role("district_admin")],
)
async def delete_school(
    school_id: str,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = SchoolService(db)
    await svc.delete_school(
        school_id,
        actor_id=str(claims.get("sub", "")),
        claims=claims,
        caller_role=_caller_role(claims),
    )
    return success({"deleted": True})
