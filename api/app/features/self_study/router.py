"""Self-study entry + state persistence API — T-209."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.core.responses import SuccessEnvelope, success
from app.features.self_study.schemas import SelfStudyEntryRead, SelfStudyStateUpdate
from app.features.self_study.service import SelfStudyEntryService

router = APIRouter(prefix="/self-study/me", tags=["self-study"])


@router.get(
    "/entry",
    response_model=SuccessEnvelope[SelfStudyEntryRead],
    operation_id="self_study_get_entry",
    summary="Enter self-study mode (resume state; independent redirects)",
)
async def get_entry(
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = SelfStudyEntryService(db)
    entry = await svc.get_entry(claims)
    return success(entry.model_dump())


@router.patch(
    "/state",
    response_model=SuccessEnvelope[SelfStudyEntryRead],
    operation_id="self_study_patch_state",
    summary="Persist last goal / material / plan view for self-study",
)
async def patch_state(
    payload: SelfStudyStateUpdate,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = SelfStudyEntryService(db)
    entry = await svc.update_state(payload, claims)
    return success(entry.model_dump())
