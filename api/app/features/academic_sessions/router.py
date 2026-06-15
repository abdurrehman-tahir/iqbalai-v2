"""Academic Session API endpoints — T-042 (Coordinator and above, §6.19)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db, require_role
from app.core.responses import SuccessEnvelope, success
from app.features.academic_sessions.schemas import (
    AcademicSessionCreate,
    AcademicSessionRead,
    ActiveSessionRead,
)
from app.features.academic_sessions.service import AcademicSessionService

router = APIRouter(prefix="/academic-sessions", tags=["academic-sessions"])


@router.get(
    "/",
    response_model=SuccessEnvelope[list[AcademicSessionRead]],
    operation_id="academic_sessions_list",
    summary="List academic sessions in the caller's school",
    dependencies=[require_role("coordinator")],
)
async def list_sessions(
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = AcademicSessionService(db)
    sessions = await svc.list_sessions(claims)
    return success([AcademicSessionRead.model_validate(s).model_dump() for s in sessions])


@router.get(
    "/active",
    response_model=SuccessEnvelope[ActiveSessionRead],
    operation_id="academic_sessions_get_active",
    summary="Get the school's active academic session",
    dependencies=[require_role("coordinator")],
)
async def get_active_session(
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = AcademicSessionService(db)
    active = await svc.get_active(claims)
    data = active.model_dump()
    if active.session is not None:
        data["session"] = AcademicSessionRead.model_validate(active.session).model_dump()
    return success(data)


@router.post(
    "/",
    response_model=SuccessEnvelope[AcademicSessionRead],
    operation_id="academic_sessions_create",
    summary="Create a new academic session",
    status_code=201,
    dependencies=[require_role("coordinator")],
)
async def create_session(
    payload: AcademicSessionCreate,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = AcademicSessionService(db)
    row = await svc.create_session(payload, claims, actor_id=str(claims.get("sub", "")))
    return success(AcademicSessionRead.model_validate(row).model_dump())


@router.post(
    "/{session_id}/activate",
    response_model=SuccessEnvelope[AcademicSessionRead],
    operation_id="academic_sessions_activate",
    summary="Mark an academic session as active (deactivates prior)",
    dependencies=[require_role("coordinator")],
)
async def activate_session(
    session_id: str,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = AcademicSessionService(db)
    row = await svc.activate_session(session_id, claims, actor_id=str(claims.get("sub", "")))
    return success(AcademicSessionRead.model_validate(row).model_dump())
