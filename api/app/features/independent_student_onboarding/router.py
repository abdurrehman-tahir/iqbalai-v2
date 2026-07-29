"""Independent student onboarding API — T-071."""

from __future__ import annotations

from typing import Any, cast

from fastapi import APIRouter, Depends
from fastapi import params as fastapi_params
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.core.exceptions import PermissionDeniedError
from app.core.responses import SuccessEnvelope, success
from app.features.independent_student_onboarding.schemas import (
    ExamFrameworkOption,
    IndependentStudentOnboardingRead,
    IndependentStudentProfileComplete,
)
from app.features.independent_student_onboarding.service import IndependentStudentOnboardingService

router = APIRouter(prefix="/independent/students/me", tags=["independent-student-onboarding"])


def require_independent_student() -> fastapi_params.Depends:
    """Dependency: caller must be exactly an independent_student.

    `require_role()`'s "X or higher" hierarchy check (ARCH §6.19) isn't meaningful
    across tenants: `independent_student`/`independent_teacher` share numeric levels
    with school-tenant roles in ROLE_HIERARCHY (both land at 1+), so
    `require_role("independent_student")` passes for ANY authenticated user, not just
    independent students — a cross-tenant access gap (T-238 follow-up finding,
    2026-07-18). This route needs an exact match instead, same pattern as
    `require_student()` in exam_frameworks/student_router.py.
    """

    def _check(claims: dict[str, object] = Depends(get_current_user)) -> dict[str, object]:
        role = str(claims.get("role", ""))
        if role != "independent_student":
            raise PermissionDeniedError("Requires an independent student account")
        return claims

    return cast(fastapi_params.Depends, Depends(_check))


@router.get(
    "/exam-frameworks",
    response_model=SuccessEnvelope[list[ExamFrameworkOption]],
    operation_id="list_independent_exam_frameworks",
    summary="List exam frameworks available for independent student signup",
    dependencies=[require_independent_student()],
)
async def list_exam_frameworks(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    svc = IndependentStudentOnboardingService(db)
    options = await svc.list_exam_frameworks()
    return success([ExamFrameworkOption.model_validate(o).model_dump() for o in options])


@router.get(
    "/onboarding",
    response_model=SuccessEnvelope[IndependentStudentOnboardingRead],
    operation_id="independent_student_get_onboarding",
    summary="Get independent student onboarding state",
    dependencies=[require_independent_student()],
)
async def get_onboarding(
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = IndependentStudentOnboardingService(db)
    state = await svc.get_onboarding_state(claims)
    return success(state.model_dump())


@router.put(
    "/profile",
    response_model=SuccessEnvelope[IndependentStudentOnboardingRead],
    operation_id="independent_student_complete_profile",
    summary="Set exam date on first login for independent students",
    dependencies=[require_independent_student()],
)
async def complete_profile(
    payload: IndependentStudentProfileComplete,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = IndependentStudentOnboardingService(db)
    state = await svc.complete_profile(payload, claims)
    return success(state.model_dump())
