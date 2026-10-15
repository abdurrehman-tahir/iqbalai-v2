"""Self-study entry, session, due-flashcards API — T-209 / T-210."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.core.responses import SuccessEnvelope, success
from app.features.self_study.schemas import (
    DueFlashcardsListRead,
    SelfStudyEntryRead,
    SelfStudySessionRead,
    SelfStudySessionStart,
    SelfStudyStateUpdate,
)
from app.features.self_study.service import SelfStudyEntryService
from app.features.self_study.session_service import SelfStudySessionService

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


@router.post(
    "/sessions",
    response_model=SuccessEnvelope[SelfStudySessionRead],
    operation_id="self_study_start_session",
    summary="Start a self-study session (Flow 6 reuse; mode=self_study events)",
)
async def start_session(
    payload: SelfStudySessionStart,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = SelfStudySessionService(db)
    row = await svc.start_session(payload, claims)
    return success(row.model_dump())


@router.post(
    "/sessions/{session_id}/end",
    response_model=SuccessEnvelope[SelfStudySessionRead],
    operation_id="self_study_end_session",
    summary="End a self-study session",
)
async def end_session(
    session_id: str,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = SelfStudySessionService(db)
    row = await svc.end_session(session_id, claims)
    return success(row.model_dump())


@router.get(
    "/due-flashcards",
    response_model=SuccessEnvelope[DueFlashcardsListRead],
    operation_id="self_study_list_due_flashcards",
    summary="Read-only due flashcards deck (schedule owned by Flow 9)",
)
async def list_due_flashcards(
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = SelfStudySessionService(db)
    deck = await svc.list_due_flashcards(claims)
    return success(deck.model_dump())
