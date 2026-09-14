"""Teaching Innovation Record API — school tenant (T-138, Flow 5 §3.10 #36)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db, require_role
from app.core.responses import SuccessEnvelope, success
from app.features.teacher_coaching import service
from app.features.teacher_coaching.schemas import CoachingResponseRequest, CoachingSuggestionRead

router = APIRouter(prefix="/teachers/me/coaching", tags=["teacher-coaching"])


@router.get(
    "",
    response_model=SuccessEnvelope[list[CoachingSuggestionRead]],
    operation_id="teacher_list_coaching_suggestions",
    summary="Pending (unactioned) coaching tips — the Teaching Innovation Record (T-138, #36)",
    dependencies=[require_role("teacher")],
)
async def list_coaching_suggestions(
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    teacher_id = await service.resolve_school_teacher_id(db, claims)
    rows = await service.list_current_suggestions_school(db, teacher_id)
    return success([service.to_suggestion_read(row).model_dump(mode="json") for row in rows])


@router.post(
    "/{memory_id}/respond",
    response_model=SuccessEnvelope[CoachingSuggestionRead],
    operation_id="teacher_respond_to_coaching_suggestion",
    summary="Mark a coaching tip acted-on or ignored (T-138, #36)",
    dependencies=[require_role("teacher")],
)
async def respond_to_coaching_suggestion(
    memory_id: str,
    payload: CoachingResponseRequest,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    teacher_id = await service.resolve_school_teacher_id(db, claims)
    memory = await service.respond_to_suggestion_school(
        db, teacher_user_id=teacher_id, memory_id=memory_id, response=payload.response
    )
    return success(service.to_suggestion_read(memory).model_dump(mode="json"))
