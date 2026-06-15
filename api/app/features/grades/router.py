"""Grade API endpoints — T-043 (Coordinator and above, §6.19)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db, require_role
from app.core.responses import SuccessEnvelope, success
from app.features.grades.schemas import GradeCreate, GradeRead, GradeUpdate
from app.features.grades.service import GradeService

router = APIRouter(prefix="/grades", tags=["grades"])


@router.get(
    "/",
    response_model=SuccessEnvelope[list[GradeRead]],
    operation_id="grades_list",
    summary="List grades for the active academic session",
    dependencies=[require_role("coordinator")],
)
async def list_grades(
    include_archived: bool = Query(default=False),
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = GradeService(db)
    grades = await svc.list_grades(claims, include_archived=include_archived)
    return success([GradeRead.model_validate(g).model_dump() for g in grades])


@router.post(
    "/",
    response_model=SuccessEnvelope[GradeRead],
    operation_id="grades_create",
    summary="Create a grade pinned to the active academic session",
    status_code=201,
    dependencies=[require_role("coordinator")],
)
async def create_grade(
    payload: GradeCreate,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = GradeService(db)
    grade = await svc.create_grade(payload, claims, actor_id=str(claims.get("sub", "")))
    return success(GradeRead.model_validate(grade).model_dump())


@router.get(
    "/{grade_id}",
    response_model=SuccessEnvelope[GradeRead],
    operation_id="grades_get",
    summary="Get a single grade",
    dependencies=[require_role("coordinator")],
)
async def get_grade(
    grade_id: str,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = GradeService(db)
    grade = await svc.get_grade(grade_id, claims)
    return success(GradeRead.model_validate(grade).model_dump())


@router.put(
    "/{grade_id}",
    response_model=SuccessEnvelope[GradeRead],
    operation_id="grades_update",
    summary="Edit a grade name",
    dependencies=[require_role("coordinator")],
)
async def update_grade(
    grade_id: str,
    payload: GradeUpdate,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = GradeService(db)
    grade = await svc.update_grade(grade_id, payload, claims, actor_id=str(claims.get("sub", "")))
    return success(GradeRead.model_validate(grade).model_dump())


@router.post(
    "/{grade_id}/archive",
    response_model=SuccessEnvelope[GradeRead],
    operation_id="grades_archive",
    summary="Archive a grade",
    dependencies=[require_role("coordinator")],
)
async def archive_grade(
    grade_id: str,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = GradeService(db)
    grade = await svc.archive_grade(grade_id, claims, actor_id=str(claims.get("sub", "")))
    return success(GradeRead.model_validate(grade).model_dump())
