"""Admin user invitation endpoints — T-030."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db, require_role
from app.core.idempotency import IdempotencyContext, idempotency_key
from app.core.responses import success
from app.features.invites.schemas import (
    AcceptInviteRequest,
    AcceptInviteResponse,
    AdminUserInviteCreate,
    UserInviteRead,
)
from app.features.invites.service import InviteService

router = APIRouter(tags=["invites"])


@router.post(
    "/admin/users",
    response_model=dict,
    summary="Invite a next-level admin (Path A)",
    operation_id="admin_users_invite",
    status_code=201,
    dependencies=[require_role("district_admin")],
)
async def invite_admin_user(
    payload: AdminUserInviteCreate,
    claims: dict = Depends(get_current_user),
    idem: IdempotencyContext | None = Depends(idempotency_key),
    db: AsyncSession = Depends(get_db),
) -> dict:
    if idem is not None:
        cached = await idem.cached_response()
        if cached is not None:
            return cached

    svc = InviteService(db)
    invite, _raw_token = await svc.create_invite(
        payload,
        actor_id=str(claims.get("sub", "")),
        caller_role=str(claims.get("role", "")),
        claims=claims,
    )
    response = success(UserInviteRead.model_validate(invite).model_dump(mode="json"))

    if idem is not None:
        await idem.store_response(response)
    return response


@router.post(
    "/admin/users/{invite_id}/resend",
    response_model=dict,
    summary="Resend an invitation with a fresh 7-day token",
    operation_id="admin_users_resend_invite",
    dependencies=[require_role("district_admin")],
)
async def resend_invite(
    invite_id: str,
    claims: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    svc = InviteService(db)
    invite, _raw_token = await svc.resend_invite(invite_id, actor_id=str(claims.get("sub", "")))
    return success(UserInviteRead.model_validate(invite).model_dump(mode="json"))


@router.post(
    "/auth/accept-invite",
    response_model=dict,
    summary="Accept or reject an admin invitation",
    operation_id="auth_accept_invite",
)
async def accept_invite(
    payload: AcceptInviteRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    svc = InviteService(db)
    result = await svc.accept_invite(payload)
    return success(AcceptInviteResponse(**result).model_dump())
