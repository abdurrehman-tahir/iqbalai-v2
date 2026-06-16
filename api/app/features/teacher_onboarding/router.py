"""Teacher onboarding API — T-053."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db, require_role
from app.core.responses import SuccessEnvelope, success
from app.features.subjects.schemas import SubjectRead
from app.features.teacher_onboarding.schemas import (
    TeacherCapacityUpdate,
    TeacherCapacityUpdateRead,
    TeacherOnboardingRead,
    TeacherProfileComplete,
)
from app.features.teacher_onboarding.service import TeacherOnboardingService

router = APIRouter(prefix="/teachers/me", tags=["teacher-onboarding"])


@router.get(
    "/onboarding",
    response_model=SuccessEnvelope[TeacherOnboardingRead],
    operation_id="teacher_get_onboarding",
    summary="Get school teacher onboarding state",
    dependencies=[require_role("teacher")],
)
async def get_onboarding(
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = TeacherOnboardingService(db)
    state = await svc.get_onboarding_state(claims)
    return success(state.model_dump())


@router.put(
    "/profile",
    response_model=SuccessEnvelope[TeacherOnboardingRead],
    operation_id="teacher_complete_profile",
    summary="Complete mandatory teacher profile on first login",
    dependencies=[require_role("teacher")],
)
async def complete_profile(
    payload: TeacherProfileComplete,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = TeacherOnboardingService(db)
    state = await svc.complete_profile(payload, claims)
    return success(state.model_dump())


@router.patch(
    "/capacity",
    response_model=SuccessEnvelope[TeacherCapacityUpdateRead],
    operation_id="teacher_update_capacity",
    summary="Update teacher self-edit capacity (1–20 grade-subject assignments)",
    dependencies=[require_role("teacher")],
)
async def update_capacity(
    payload: TeacherCapacityUpdate,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = TeacherOnboardingService(db)
    result = await svc.update_capacity(payload, claims)
    return success(result.model_dump())


@router.get(
    "/subject-options",
    response_model=SuccessEnvelope[list[SubjectRead]],
    operation_id="teacher_list_subject_options",
    summary="List active school subjects for profile completion",
    dependencies=[require_role("teacher")],
)
async def list_subject_options(
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = TeacherOnboardingService(db)
    subjects = await svc.list_subject_options(claims)
    return success([SubjectRead.model_validate(s).model_dump() for s in subjects])
