"""Student graduation status endpoint — T-085."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db, require_role
from app.core.responses import SuccessEnvelope, success
from app.features.graduation.schemas import StudentGraduationStatusRead
from app.features.graduation.service import GraduationService

router = APIRouter(prefix="/students/me", tags=["graduation"])


@router.get(
    "/graduation",
    response_model=SuccessEnvelope[StudentGraduationStatusRead],
    operation_id="student_get_graduation_status",
    summary="Get school student graduation / read-only status",
    dependencies=[require_role("student")],
)
async def get_graduation_status(
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = GraduationService(db)
    status = await svc.get_student_graduation_status(claims)
    return success(status.model_dump())
