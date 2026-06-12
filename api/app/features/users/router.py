"""User endpoints — T-016 (me endpoint)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.core.exceptions import NotFoundError
from app.core.responses import SuccessEnvelope, success
from app.features.users.schemas import UserRead
from app.features.users.service import UserService

router = APIRouter(prefix="/users", tags=["users"])


@router.get(
    "/me",
    response_model=SuccessEnvelope[UserRead],
    operation_id="get_me",
    summary="Get current user profile",
)
async def get_me(
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = UserService(db)
    user = await svc.get_me(str(claims.get("sub", "")))
    if user is None:
        raise NotFoundError("User profile not found — call /auth/post-login first")
    return success(UserRead.model_validate(user).model_dump())
