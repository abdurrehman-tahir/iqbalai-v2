"""Public independent signup endpoints — T-069."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db
from app.core.responses import SuccessEnvelope, success
from app.features.independent_signup.schemas import (
    IndependentSignupCreate,
    IndependentSignupInfo,
    IndependentSignupResponse,
)
from app.features.independent_signup.service import IndependentSignupService

router = APIRouter(prefix="/independent/signup", tags=["independent-signup"])


@router.get(
    "",
    response_model=SuccessEnvelope[IndependentSignupInfo],
    operation_id="get_independent_signup_info",
    summary="Independent signup form metadata",
)
async def get_independent_signup_info(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    svc = IndependentSignupService(db)
    info = await svc.get_signup_info()
    return success(IndependentSignupInfo.model_validate(info).model_dump())


@router.post(
    "",
    response_model=SuccessEnvelope[IndependentSignupResponse],
    operation_id="create_independent_signup",
    status_code=201,
    summary="Self-signup for independent teachers and students",
)
async def create_independent_signup(
    payload: IndependentSignupCreate,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = IndependentSignupService(db)
    result = await svc.signup(payload)
    return success(IndependentSignupResponse.model_validate(result).model_dump())
