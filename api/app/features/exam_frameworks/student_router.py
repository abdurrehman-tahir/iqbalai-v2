"""Student-facing exam-framework routes — browse, select, render, switch, drop (T-096).

Serves both tenant types (school + independent students). Region + grade are query
params supplied by the caller (a student's region is not yet stored on the profile; the
filtering *engine* is what this ticket builds). The pinned §3.5.2 plan renders into a
learnable study-plan UI and is the self-study integration hook (Flow 8 / M-08+).
"""

from __future__ import annotations

from typing import Any, cast

import structlog
from fastapi import APIRouter, Depends, Query
from fastapi import params as fastapi_params
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.core.exceptions import PermissionDeniedError
from app.core.responses import SuccessEnvelope, success
from app.features.exam_frameworks.schemas import (
    AvailableFrameworkRead,
    StudentSelectionRead,
    StudentStudyPlanRead,
)
from app.features.exam_frameworks.student_service import (
    AvailableFramework,
    SelectionView,
    StudentFrameworkService,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/student/exam-frameworks", tags=["exam_frameworks_student"])

# School students and independent students share this surface; both write to the same
# platform-shared selections table (§3.16). Higher-privilege roles are not students.
_STUDENT_ROLES = {"student", "independent_student"}


def require_student() -> fastapi_params.Depends:
    """Dependency: caller must be a school or independent student (exact role check)."""

    def _check(claims: dict[str, object] = Depends(get_current_user)) -> dict[str, object]:
        role = str(claims.get("role", ""))
        if role not in _STUDENT_ROLES:
            logger.warning("permission_denied", caller_role=role, required="student")
            raise PermissionDeniedError("Requires a student account")
        return claims

    return cast(fastapi_params.Depends, Depends(_check))


def _available_read(item: AvailableFramework) -> dict[str, Any]:
    fw = item.framework
    return AvailableFrameworkRead(
        id=fw.id,
        name=fw.name,
        exam_target=fw.exam_target,
        region=fw.region,
        target_grade_range=fw.target_grade_range,
        language=fw.language,
        current_version=item.current_version,
    ).model_dump()


def _selection_read(view: SelectionView) -> dict[str, Any]:
    sel = view.selection
    return StudentSelectionRead(
        id=sel.id,
        framework_id=sel.framework_id,
        framework_name=view.framework.name,
        exam_target=view.framework.exam_target,
        pinned_version=sel.pinned_version,
        latest_version=view.latest_version,
        update_available=view.update_available,
        status=sel.status,
        selected_at=sel.selected_at,
    ).model_dump()


@router.get(
    "/available",
    response_model=SuccessEnvelope[list[AvailableFrameworkRead]],
    operation_id="student_frameworks_available",
    summary="Browse selectable frameworks (region + grade scoped)",
    dependencies=[require_student()],
)
async def list_available(
    region: str = Query(
        ..., min_length=1, description="Student's region (matches region or 'any')"
    ),
    grade: int = Query(..., ge=1, le=14, description="Student's grade level"),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = StudentFrameworkService(db)
    items = await svc.list_available(region=region, grade=grade)
    return success([_available_read(i) for i in items])


@router.post(
    "/{framework_id}/select",
    response_model=SuccessEnvelope[StudentSelectionRead],
    operation_id="student_frameworks_select",
    summary="Select a framework (ACTIVE, pinned to the current version)",
    status_code=201,
    dependencies=[require_student()],
)
async def select_framework(
    framework_id: str,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = StudentFrameworkService(db)
    tenant_type, student_user_id = await svc.resolve_student(claims)
    view = await svc.select(framework_id, tenant_type, student_user_id)
    return success(_selection_read(view))


@router.get(
    "/selections",
    response_model=SuccessEnvelope[list[StudentSelectionRead]],
    operation_id="student_frameworks_selections",
    summary="List my framework selections (with opt-in update flag)",
    dependencies=[require_student()],
)
async def list_selections(
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = StudentFrameworkService(db)
    tenant_type, student_user_id = await svc.resolve_student(claims)
    views = await svc.list_my_selections(tenant_type, student_user_id)
    return success([_selection_read(v) for v in views])


@router.get(
    "/selections/{selection_id}/study-plan",
    response_model=SuccessEnvelope[StudentStudyPlanRead],
    operation_id="student_frameworks_study_plan",
    summary="Render the pinned study plan for a selection (self-study hook)",
    dependencies=[require_student()],
)
async def get_study_plan(
    selection_id: str,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = StudentFrameworkService(db)
    tenant_type, student_user_id = await svc.resolve_student(claims)
    framework, plan = await svc.get_selection_study_plan(selection_id, tenant_type, student_user_id)
    return success(
        StudentStudyPlanRead(
            framework_id=framework.id,
            framework_name=framework.name,
            exam_target=framework.exam_target,
            version=plan.version,
            content_jsonb=plan.content_jsonb,
            generated_at=plan.generated_at,
        ).model_dump()
    )


@router.post(
    "/selections/{selection_id}/switch",
    response_model=SuccessEnvelope[StudentSelectionRead],
    operation_id="student_frameworks_switch",
    summary="Opt in to the latest published version for a selection",
    dependencies=[require_student()],
)
async def switch_version(
    selection_id: str,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = StudentFrameworkService(db)
    tenant_type, student_user_id = await svc.resolve_student(claims)
    view = await svc.switch_version(selection_id, tenant_type, student_user_id)
    return success(_selection_read(view))


@router.delete(
    "/selections/{selection_id}",
    response_model=SuccessEnvelope[StudentSelectionRead],
    operation_id="student_frameworks_drop",
    summary="Drop a selection (-> ABANDONED; history retained)",
    dependencies=[require_student()],
)
async def drop_selection(
    selection_id: str,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = StudentFrameworkService(db)
    tenant_type, student_user_id = await svc.resolve_student(claims)
    view = await svc.drop(selection_id, tenant_type, student_user_id)
    return success(_selection_read(view))
