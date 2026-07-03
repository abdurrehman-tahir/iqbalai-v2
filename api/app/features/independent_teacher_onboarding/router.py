"""Independent teacher onboarding API — T-070."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db, require_role
from app.core.responses import SuccessEnvelope, success
from app.features.independent_teacher_onboarding.schemas import (
    IndependentTeacherOnboardingRead,
    IndependentTeacherProfileComplete,
)
from app.features.independent_teacher_onboarding.service import IndependentTeacherOnboardingService

router = APIRouter(prefix="/independent/teachers/me", tags=["independent-teacher-onboarding"])


@router.get(
    "/onboarding",
    response_model=SuccessEnvelope[IndependentTeacherOnboardingRead],
    operation_id="independent_teacher_get_onboarding",
    summary="Get independent teacher onboarding state",
    dependencies=[require_role("independent_teacher")],
)
async def get_onboarding(
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = IndependentTeacherOnboardingService(db)
    state = await svc.get_onboarding_state(claims)
    return success(state.model_dump())


@router.put(
    "/profile",
    response_model=SuccessEnvelope[IndependentTeacherOnboardingRead],
    operation_id="independent_teacher_complete_profile",
    summary="Complete mandatory independent teacher profile on first login",
    dependencies=[require_role("independent_teacher")],
)
async def complete_profile(
    payload: IndependentTeacherProfileComplete,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = IndependentTeacherOnboardingService(db)
    state = await svc.complete_profile(payload, claims)
    return success(state.model_dump())
