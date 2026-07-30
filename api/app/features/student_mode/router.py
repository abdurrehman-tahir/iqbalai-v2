"""School student mode switcher API — T-101."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.core.responses import SuccessEnvelope, success
from app.features.student_mode.schemas import StudentModeRead, StudentModeUpdate
from app.features.student_mode.service import StudentModeService

router = APIRouter(prefix="/students/me", tags=["student-mode"])


@router.get(
    "/mode",
    response_model=SuccessEnvelope[StudentModeRead],
    operation_id="student_get_mode",
    summary="Get school student active study mode",
)
async def get_mode(
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = StudentModeService(db)
    state = await svc.get_mode(claims)
    return success(state.model_dump())


@router.put(
    "/mode",
    response_model=SuccessEnvelope[StudentModeRead],
    operation_id="student_set_mode",
    summary="Switch school student Lecture ⇄ Self-Study mode",
)
async def set_mode(
    payload: StudentModeUpdate,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = StudentModeService(db)
    state = await svc.set_mode(payload, claims, actor_id=str(claims.get("sub", "")))
    return success(state.model_dump())
