"""School student onboarding API — T-078."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db, require_role
from app.core.responses import SuccessEnvelope, success
from app.features.student_onboarding.schemas import (
    SchoolStudentOnboardingRead,
    StudentBannerDismiss,
    StudentExamDateUpdate,
    StudentModeSelect,
    StudentProfileBasicComplete,
)
from app.features.student_onboarding.service import StudentOnboardingService

router = APIRouter(prefix="/students/me", tags=["student-onboarding"])


def _client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


@router.get(
    "/onboarding",
    response_model=SuccessEnvelope[SchoolStudentOnboardingRead],
    operation_id="student_get_onboarding",
    summary="Get school student onboarding state",
    dependencies=[require_role("student")],
)
async def get_onboarding(
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = StudentOnboardingService(db)
    state = await svc.get_onboarding_state(claims)
    return success(state.model_dump())


@router.put(
    "/onboarding/profile-basic",
    response_model=SuccessEnvelope[SchoolStudentOnboardingRead],
    operation_id="student_complete_profile_basic",
    summary="Complete mandatory profile basics (name, language, ToS)",
    dependencies=[require_role("student")],
)
async def complete_profile_basic(
    payload: StudentProfileBasicComplete,
    request: Request,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = StudentOnboardingService(db)
    state = await svc.complete_profile_basic(
        payload,
        claims,
        actor_id=str(claims.get("sub", "")),
        ip_address=_client_ip(request),
    )
    return success(state.model_dump())


@router.put(
    "/onboarding/modes",
    response_model=SuccessEnvelope[SchoolStudentOnboardingRead],
    operation_id="student_select_modes",
    summary="Select at least one study mode to reach READY_TO_STUDY",
    dependencies=[require_role("student")],
)
async def select_modes(
    payload: StudentModeSelect,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = StudentOnboardingService(db)
    state = await svc.select_modes(payload, claims, actor_id=str(claims.get("sub", "")))
    return success(state.model_dump())


@router.post(
    "/onboarding/dismiss-banner",
    response_model=SuccessEnvelope[SchoolStudentOnboardingRead],
    operation_id="student_dismiss_profile_banner",
    summary="Dismiss the optional complete-your-profile banner",
    dependencies=[require_role("student")],
)
async def dismiss_banner(
    _payload: StudentBannerDismiss,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = StudentOnboardingService(db)
    state = await svc.dismiss_profile_banner(claims, actor_id=str(claims.get("sub", "")))
    return success(state.model_dump())


@router.put(
    "/onboarding/exam-date",
    response_model=SuccessEnvelope[SchoolStudentOnboardingRead],
    operation_id="student_set_exam_date",
    summary="Set or update deferrable exam date",
    dependencies=[require_role("student")],
)
async def set_exam_date(
    payload: StudentExamDateUpdate,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = StudentOnboardingService(db)
    state = await svc.set_exam_date(payload, claims, actor_id=str(claims.get("sub", "")))
    return success(state.model_dump())
