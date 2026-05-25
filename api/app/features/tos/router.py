"""ToS and Disclaimer API endpoints — T-016 + T-019."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db, require_role
from app.core.responses import success
from app.features.tos.schemas import (
    DisclaimerVersionCreate,
    DisclaimerVersionRead,
    TosAcceptRequest,
    TosAcceptResponse,
    TosVersionCreate,
    TosVersionRead,
)
from app.features.tos.service import TosService

router = APIRouter()

# ── Public read endpoints (no auth needed for current ToS/Disclaimer) ─────────


@router.get(
    "/tos/current",
    response_model=dict,
    summary="Get current ToS version",
    tags=["tos"],
)
async def get_current_tos(db: AsyncSession = Depends(get_db)) -> dict:
    svc = TosService(db)
    tos = await svc.get_current_tos()
    return success(TosVersionRead.model_validate(tos).model_dump())


@router.get(
    "/tos/versions",
    response_model=dict,
    summary="List all ToS versions",
    tags=["tos"],
)
async def list_tos_versions(db: AsyncSession = Depends(get_db)) -> dict:
    svc = TosService(db)
    versions = await svc.list_tos_versions()
    return success([TosVersionRead.model_validate(v).model_dump() for v in versions])


@router.get(
    "/disclaimer/current",
    response_model=dict,
    summary="Get current Disclaimer version",
    tags=["tos"],
)
async def get_current_disclaimer(db: AsyncSession = Depends(get_db)) -> dict:
    svc = TosService(db)
    disclaimer = await svc.get_current_disclaimer()
    return success(DisclaimerVersionRead.model_validate(disclaimer).model_dump())


# ── User acceptance endpoint ──────────────────────────────────────────────────


@router.post(
    "/users/me/accept-tos",
    response_model=dict,
    summary="Accept the current ToS",
    tags=["tos"],
)
async def accept_tos(
    payload: TosAcceptRequest,
    request: Request,
    claims: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    svc = TosService(db)
    user_id = str(claims.get("sub", ""))
    ip = request.client.host if request.client else None
    acceptance = await svc.accept_tos(user_id, payload.tos_version_id, ip)
    resp = TosAcceptResponse(
        accepted=True,
        tos_version_id=payload.tos_version_id,
        accepted_at=acceptance.accepted_at,
    )
    return success(resp.model_dump())


# ── Admin endpoints (Platform Admin only) ─────────────────────────────────────


@router.post(
    "/admin/tos",
    response_model=dict,
    summary="Publish a new ToS version",
    tags=["tos"],
    dependencies=[require_role("platform_admin")],
)
async def publish_tos(
    payload: TosVersionCreate,
    claims: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    svc = TosService(db)
    tos = await svc.publish_new_tos(
        content_md=payload.content_md,
        language=payload.language,
        published_by=str(claims.get("sub", "")),
    )
    return success(TosVersionRead.model_validate(tos).model_dump())


@router.get(
    "/admin/tos",
    response_model=dict,
    summary="List all ToS versions (admin)",
    tags=["tos"],
    dependencies=[require_role("platform_admin")],
)
async def admin_list_tos(db: AsyncSession = Depends(get_db)) -> dict:
    svc = TosService(db)
    versions = await svc.list_tos_versions()
    return success([TosVersionRead.model_validate(v).model_dump() for v in versions])


@router.post(
    "/admin/disclaimer",
    response_model=dict,
    summary="Publish a new Disclaimer version",
    tags=["tos"],
    dependencies=[require_role("platform_admin")],
)
async def publish_disclaimer(
    payload: DisclaimerVersionCreate,
    claims: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    svc = TosService(db)
    disclaimer = await svc.publish_new_disclaimer(
        content=payload.content,
        language=payload.language,
        published_by=str(claims.get("sub", "")),
    )
    return success(DisclaimerVersionRead.model_validate(disclaimer).model_dump())


@router.get(
    "/admin/disclaimer",
    response_model=dict,
    summary="List all Disclaimer versions (admin)",
    tags=["tos"],
    dependencies=[require_role("platform_admin")],
)
async def admin_list_disclaimer(db: AsyncSession = Depends(get_db)) -> dict:
    svc = TosService(db)
    versions = await svc.list_disclaimer_versions()
    return success([DisclaimerVersionRead.model_validate(v).model_dump() for v in versions])
