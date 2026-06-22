"""Public parent signup endpoints — T-080."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db
from app.core.responses import SuccessEnvelope, success
from app.features.parent_signup.schemas import (
    ParentSignupCreate,
    ParentSignupInfo,
    ParentSignupResponse,
)
from app.features.parent_signup.service import ParentSignupService

router = APIRouter(prefix="/parents/signup", tags=["parent-signup"])


@router.get(
    "",
    response_model=SuccessEnvelope[ParentSignupInfo],
    operation_id="get_parent_signup_info",
    summary="Parent signup form metadata",
)
async def get_parent_signup_info() -> dict[str, Any]:
    info = ParentSignupService.signup_info()
    return success(ParentSignupInfo.model_validate(info).model_dump())


@router.post(
    "",
    response_model=SuccessEnvelope[ParentSignupResponse],
    operation_id="create_parent_signup",
    status_code=201,
    summary="Self-signup for parents of school students",
)
async def create_parent_signup(
    payload: ParentSignupCreate,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = ParentSignupService(db)
    result = await svc.signup(payload)
    return success(ParentSignupResponse.model_validate(result).model_dump())
