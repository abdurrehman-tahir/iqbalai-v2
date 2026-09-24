"""Student #72 teacher-share privacy API — T-162."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.core.responses import SuccessEnvelope, success
from app.features.student_privacy.schemas import (
    TeacherActivityShareRead,
    TeacherActivityShareUpdate,
)
from app.features.student_privacy.service import StudentPrivacyService

router = APIRouter(prefix="/students/me/privacy", tags=["student-privacy"])


@router.get(
    "/teacher-share",
    response_model=SuccessEnvelope[TeacherActivityShareRead],
    operation_id="student_get_teacher_activity_share",
    summary="Get #72 share-with-teacher preference (default share)",
)
async def get_teacher_activity_share(
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    result = await StudentPrivacyService(db).get_teacher_share(claims)
    return success(result.model_dump())


@router.patch(
    "/teacher-share",
    response_model=SuccessEnvelope[TeacherActivityShareRead],
    operation_id="student_set_teacher_activity_share",
    summary="Toggle #72 share-with-teacher preference (audit-logged)",
)
async def set_teacher_activity_share(
    payload: TeacherActivityShareUpdate,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    result = await StudentPrivacyService(db).set_teacher_share(
        payload, claims, actor_id=str(claims.get("sub", ""))
    )
    return success(result.model_dump())
