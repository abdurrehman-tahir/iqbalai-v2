"""Exam Framework definition CRUD — Platform Admin only (T-092, ARCH §3.19/§6.19).

Platform Admin creates/edits/deletes framework definitions in DRAFT. Every route
requires ``platform_admin`` (top of the hierarchy) — non-Platform-Admin callers are
denied with 403 PERMISSION_DENIED. Edit/delete are gated to DRAFT status; once
research runs (T-093) the record leaves DRAFT.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db, require_role
from app.core.responses import SuccessEnvelope, success
from app.features.exam_frameworks.models import FrameworkStatus
from app.features.exam_frameworks.schemas import (
    ExamFrameworkCreate,
    ExamFrameworkRead,
    ExamFrameworkUpdate,
    FrameworkResearchJobRead,
)
from app.features.exam_frameworks.service import ExamFrameworkService

router = APIRouter(prefix="/exam-frameworks", tags=["exam_frameworks"])


@router.get(
    "/",
    response_model=SuccessEnvelope[list[ExamFrameworkRead]],
    operation_id="exam_frameworks_list",
    summary="List exam-framework definitions",
    dependencies=[require_role("platform_admin")],
)
async def list_frameworks(
    status: FrameworkStatus | None = Query(default=None, description="Filter by status"),
    include_deleted: bool = Query(default=False, description="Include soft-deleted definitions"),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = ExamFrameworkService(db)
    frameworks = await svc.list_frameworks(status=status, include_deleted=include_deleted)
    return success([ExamFrameworkRead.model_validate(f).model_dump() for f in frameworks])


@router.post(
    "/",
    response_model=SuccessEnvelope[ExamFrameworkRead],
    operation_id="exam_frameworks_create",
    summary="Create a DRAFT exam-framework definition",
    status_code=201,
    dependencies=[require_role("platform_admin")],
)
async def create_framework(
    payload: ExamFrameworkCreate,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = ExamFrameworkService(db)
    framework = await svc.create_framework(payload, actor_id=str(claims.get("sub", "")))
    return success(ExamFrameworkRead.model_validate(framework).model_dump())


@router.get(
    "/{framework_id}",
    response_model=SuccessEnvelope[ExamFrameworkRead],
    operation_id="exam_frameworks_get",
    summary="Get a single exam-framework definition",
    dependencies=[require_role("platform_admin")],
)
async def get_framework(
    framework_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = ExamFrameworkService(db)
    framework = await svc.get_framework(framework_id)
    return success(ExamFrameworkRead.model_validate(framework).model_dump())


@router.put(
    "/{framework_id}",
    response_model=SuccessEnvelope[ExamFrameworkRead],
    operation_id="exam_frameworks_update",
    summary="Edit a DRAFT exam-framework definition",
    dependencies=[require_role("platform_admin")],
)
async def update_framework(
    framework_id: str,
    payload: ExamFrameworkUpdate,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = ExamFrameworkService(db)
    framework = await svc.update_framework(
        framework_id, payload, actor_id=str(claims.get("sub", ""))
    )
    return success(ExamFrameworkRead.model_validate(framework).model_dump())


@router.delete(
    "/{framework_id}",
    response_model=SuccessEnvelope[ExamFrameworkRead],
    operation_id="exam_frameworks_delete",
    summary="Soft-delete a DRAFT exam-framework definition",
    dependencies=[require_role("platform_admin")],
)
async def delete_framework(
    framework_id: str,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = ExamFrameworkService(db)
    framework = await svc.delete_framework(framework_id, actor_id=str(claims.get("sub", "")))
    return success(ExamFrameworkRead.model_validate(framework).model_dump())


@router.post(
    "/{framework_id}/research",
    response_model=SuccessEnvelope[FrameworkResearchJobRead],
    operation_id="exam_frameworks_trigger_research",
    summary="Trigger the Pattern-A AI research run for a DRAFT framework",
    status_code=202,
    dependencies=[require_role("platform_admin")],
)
async def trigger_research(
    framework_id: str,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = ExamFrameworkService(db)
    job = await svc.trigger_research(framework_id, actor_id=str(claims.get("sub", "")))
    return success(FrameworkResearchJobRead.model_validate(job).model_dump())


@router.get(
    "/{framework_id}/research",
    response_model=SuccessEnvelope[FrameworkResearchJobRead],
    operation_id="exam_frameworks_latest_research",
    summary="Get the latest AI research job for a framework (progress/result)",
    dependencies=[require_role("platform_admin")],
)
async def latest_research(
    framework_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = ExamFrameworkService(db)
    job = await svc.get_latest_job(framework_id)
    return success(FrameworkResearchJobRead.model_validate(job).model_dump())
