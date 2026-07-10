"""Admin user management endpoints — lifecycle (T-033)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db, require_role
from app.core.responses import success
from app.features.users.lifecycle_service import UserLifecycleService
from app.features.users.schemas import UserRead

router = APIRouter(prefix="/admin/users", tags=["admin-users"])


def _caller_role(claims: dict[str, object]) -> str:
    return str(claims.get("role", ""))


@router.get(
    "/",
    response_model=dict,
    summary="List users in caller's scope",
    operation_id="admin_users_list",
    dependencies=[require_role("school_admin")],
)
async def list_users(
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = UserLifecycleService(db)
    users = await svc.list_users(claims, _caller_role(claims))
    return success([UserRead.model_validate(u).model_dump() for u in users])


@router.post(
    "/{user_id}/suspend",
    response_model=dict,
    summary="Suspend a user account",
    operation_id="admin_users_suspend",
    dependencies=[require_role("school_admin")],
)
async def suspend_user(
    user_id: str,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = UserLifecycleService(db)
    user = await svc.suspend_user(
        user_id,
        claims=claims,
        actor_id=str(claims.get("sub", "")),
    )
    return success(UserRead.model_validate(user).model_dump())


@router.post(
    "/{user_id}/reactivate",
    response_model=dict,
    summary="Reactivate a suspended user account",
    operation_id="admin_users_reactivate",
    dependencies=[require_role("school_admin")],
)
async def reactivate_user(
    user_id: str,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = UserLifecycleService(db)
    user = await svc.reactivate_user(
        user_id,
        claims=claims,
        actor_id=str(claims.get("sub", "")),
    )
    return success(UserRead.model_validate(user).model_dump())


@router.post(
    "/{user_id}/deactivate",
    response_model=dict,
    summary="Permanently deactivate a user account (one-way)",
    operation_id="admin_users_deactivate",
    dependencies=[require_role("school_admin")],
)
async def deactivate_user(
    user_id: str,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = UserLifecycleService(db)
    user = await svc.deactivate_user(
        user_id,
        claims=claims,
        actor_id=str(claims.get("sub", "")),
    )
    return success(UserRead.model_validate(user).model_dump())
