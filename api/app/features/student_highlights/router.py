"""Student highlights HTTP API — T-185 (yellow-mark restore)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db, require_role
from app.core.responses import SuccessEnvelope, success
from app.features.student_highlights.schemas import StudentHighlightRead
from app.features.student_highlights.service import StudentHighlightService

router = APIRouter(prefix="/students/me", tags=["student-highlights"])


@router.get(
    "/lectures/{lecture_id}/highlights",
    response_model=SuccessEnvelope[list[StudentHighlightRead]],
    operation_id="student_list_lecture_highlights",
    summary="List own highlights on a lecture with current yellow-mark positions (T-185)",
    dependencies=[require_role("student")],
)
async def list_lecture_highlights(
    lecture_id: str,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    rows = await StudentHighlightService(db).list_for_lecture(claims, lecture_id)
    return success([r.model_dump(mode="json") for r in rows])
