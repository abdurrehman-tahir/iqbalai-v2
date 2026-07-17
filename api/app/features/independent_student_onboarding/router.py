"""Independent student onboarding API — T-071."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db, require_role
from app.core.responses import SuccessEnvelope, success
from app.features.independent_student_onboarding.schemas import (
    ExamFrameworkOption,
    IndependentStudentOnboardingRead,
    IndependentStudentProfileComplete,
)
from app.features.independent_student_onboarding.service import IndependentStudentOnboardingService

router = APIRouter(prefix="/independent/students/me", tags=["independent-student-onboarding"])


@router.get(
    "/exam-frameworks",
    response_model=SuccessEnvelope[list[ExamFrameworkOption]],
    operation_id="list_independent_exam_frameworks",
    summary="List exam frameworks available for independent student signup",
    dependencies=[require_role("independent_student")],
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
    dependencies=[require_role("independent_student")],
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
    dependencies=[require_role("independent_student")],
)
async def complete_profile(
    payload: IndependentStudentProfileComplete,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = IndependentStudentOnboardingService(db)
    state = await svc.complete_profile(payload, claims)
    return success(state.model_dump())
