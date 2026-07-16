"""ToS and Disclaimer API endpoints — T-016 + T-019."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db, require_role
from app.core.exceptions import NotFoundError
from app.core.responses import SuccessEnvelope, success
from app.core.tenant import TenantType, get_tenant_type
from app.features.independent_users.service import IndependentUserService
from app.features.tos.schemas import (
    DisclaimerVersionCreate,
    DisclaimerVersionRead,
    TosAcceptRequest,
    TosAcceptResponse,
    TosDeclineResponse,
    TosVersionCreate,
    TosVersionRead,
)
from app.features.tos.service import TosService
from app.features.users.service import UserService

router = APIRouter()


async def _resolve_caller(claims: dict[str, object], db: AsyncSession) -> tuple[str, TenantType]:
    """Resolve the caller's app-user id in whichever tenant owns them.

    Independent users are created by ``/auth/post-login`` into independent.users and have
    no row in school.users, so looking them up via UserService alone 404'd every
    independent teacher/student at the ToS gate — the last step of their first login
    (QA E10/E11).
    """
    authentik_id = str(claims.get("sub", ""))
    tenant_type = get_tenant_type(claims)

    if tenant_type == "independent":
        independent_user = await IndependentUserService(db).get_me(authentik_id)
        if independent_user is None:
            raise NotFoundError("User profile not found — call /auth/post-login first")
        return independent_user.id, tenant_type

    school_user = await UserService(db).get_me(authentik_id)
    if school_user is None:
        raise NotFoundError("User profile not found — call /auth/post-login first")
    return school_user.id, tenant_type


# ── Public read endpoints (no auth needed for current ToS/Disclaimer) ─────────


@router.get(
    "/tos/current",
    response_model=SuccessEnvelope[TosVersionRead],
    operation_id="get_current_tos",
    summary="Get current ToS version",
    tags=["tos"],
)
async def get_current_tos(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    svc = TosService(db)
    tos = await svc.get_current_tos()
    return success(TosVersionRead.model_validate(tos).model_dump())


@router.get(
    "/tos/versions",
    response_model=SuccessEnvelope[list[TosVersionRead]],
    operation_id="list_tos_versions",
    summary="List all ToS versions",
    tags=["tos"],
)
async def list_tos_versions(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    svc = TosService(db)
    versions = await svc.list_tos_versions()
    return success([TosVersionRead.model_validate(v).model_dump() for v in versions])


@router.get(
    "/disclaimer/current",
    response_model=SuccessEnvelope[DisclaimerVersionRead],
    operation_id="get_current_disclaimer",
    summary="Get current Disclaimer version",
    tags=["tos"],
)
async def get_current_disclaimer(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    svc = TosService(db)
    disclaimer = await svc.get_current_disclaimer()
    return success(DisclaimerVersionRead.model_validate(disclaimer).model_dump())


# ── User acceptance endpoint ──────────────────────────────────────────────────


@router.post(
    "/users/me/accept-tos",
    response_model=SuccessEnvelope[TosAcceptResponse],
    operation_id="accept_tos",
    summary="Accept the current ToS",
    tags=["tos"],
)
async def accept_tos(
    payload: TosAcceptRequest,
    request: Request,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    user_id, tenant_type = await _resolve_caller(claims, db)
    ip = request.client.host if request.client else None
    acceptance = await TosService(db).accept_tos(
        user_id, payload.tos_version_id, ip, tenant_type=tenant_type
    )
    resp = TosAcceptResponse(
        accepted=True,
        tos_version_id=payload.tos_version_id,
        accepted_at=acceptance.accepted_at,
    )
    return success(resp.model_dump())


@router.post(
    "/users/me/decline-tos",
    response_model=SuccessEnvelope[TosDeclineResponse],
    operation_id="decline_tos",
    summary="Decline the current ToS",
    tags=["tos"],
)
async def decline_tos(
    request: Request,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    user_id, tenant_type = await _resolve_caller(claims, db)
    ip = request.client.host if request.client else None
    await TosService(db).decline_tos(user_id, ip, tenant_type=tenant_type)
    return success(TosDeclineResponse(declined=True).model_dump())


# ── Admin endpoints (Platform Admin only) ─────────────────────────────────────


@router.post(
    "/admin/tos",
    response_model=SuccessEnvelope[TosVersionRead],
    operation_id="publish_tos",
    summary="Publish a new ToS version",
    tags=["tos"],
    dependencies=[require_role("platform_admin")],
)
async def publish_tos(
    payload: TosVersionCreate,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = TosService(db)
    tos = await svc.publish_new_tos(
        content_md=payload.content_md,
        language=payload.language,
        published_by=str(claims.get("sub", "")),
    )
    return success(TosVersionRead.model_validate(tos).model_dump())


@router.get(
    "/admin/tos",
    response_model=SuccessEnvelope[list[TosVersionRead]],
    operation_id="admin_list_tos",
    summary="List all ToS versions (admin)",
    tags=["tos"],
    dependencies=[require_role("platform_admin")],
)
async def admin_list_tos(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    svc = TosService(db)
    versions = await svc.list_tos_versions()
    return success([TosVersionRead.model_validate(v).model_dump() for v in versions])


@router.post(
    "/admin/disclaimer",
    response_model=SuccessEnvelope[DisclaimerVersionRead],
    operation_id="publish_disclaimer",
    summary="Publish a new Disclaimer version",
    tags=["tos"],
    dependencies=[require_role("platform_admin")],
)
async def publish_disclaimer(
    payload: DisclaimerVersionCreate,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = TosService(db)
    disclaimer = await svc.publish_new_disclaimer(
        content=payload.content,
        language=payload.language,
        published_by=str(claims.get("sub", "")),
    )
    return success(DisclaimerVersionRead.model_validate(disclaimer).model_dump())


@router.get(
    "/admin/disclaimer",
    response_model=SuccessEnvelope[list[DisclaimerVersionRead]],
    operation_id="admin_list_disclaimer",
    summary="List all Disclaimer versions (admin)",
    tags=["tos"],
    dependencies=[require_role("platform_admin")],
)
async def admin_list_disclaimer(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    svc = TosService(db)
    versions = await svc.list_disclaimer_versions()
    return success([DisclaimerVersionRead.model_validate(v).model_dump() for v in versions])
