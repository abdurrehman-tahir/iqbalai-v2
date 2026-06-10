"""Auth endpoints — T-016 (post-login OIDC callback handler)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.core.responses import SuccessEnvelope, success
from app.features.auth.schemas import PostLoginResponse
from app.features.auth.service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/post-login",
    response_model=SuccessEnvelope[PostLoginResponse],
    operation_id="post_login",
    summary="Post-OIDC-login handler",
    description=(
        "Called by the frontend after every successful Authentik OIDC callback. "
        "Creates a User row on first login. Returns ToS acceptance status so the "
        "frontend can show the acceptance modal if needed."
    ),
)
async def post_login(
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = AuthService(db)
    result = await svc.post_login(claims)
    return success(PostLoginResponse.model_validate(result).model_dump())
