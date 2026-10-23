"""Next-day review API — M-16 (Flow 7). School tenant only.

``require_role("teacher")`` is the floor (teacher or higher, ARCH §6.19 / A-001);
per-review scope and the teacher-only / override rules live in the service.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db, require_role
from app.core.responses import SuccessEnvelope, success
from app.features.next_day_review.schemas import (
    ReflectionCreate,
    ReviewDetailRead,
    ReviewSummaryRead,
)
from app.features.next_day_review.service import NextDayReviewService

router = APIRouter(prefix="/reviews", tags=["next-day-review"])


@router.get(
    "",
    response_model=SuccessEnvelope[list[ReviewSummaryRead]],
    operation_id="list_next_day_reviews",
    summary="Next-day review cards in the caller's scope, newest first (T-201 / T-206)",
    dependencies=[require_role("teacher")],
)
async def list_reviews(
    lecture_id: str | None = Query(default=None, max_length=36),
    claims: dict[str, Any] = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    rows = await NextDayReviewService(session).list_reviews(claims, lecture_id=lecture_id)
    return success([r.model_dump(mode="json") for r in rows])


@router.get(
    "/{review_id}",
    response_model=SuccessEnvelope[ReviewDetailRead],
    operation_id="get_next_day_review",
    summary="One review card with clusters, mini-lecture preview and replies (T-201 / T-203)",
    dependencies=[require_role("teacher")],
)
async def get_review(
    review_id: str,
    claims: dict[str, Any] = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    detail = await NextDayReviewService(session).get_review(claims, review_id)
    return success(detail.model_dump(mode="json"))


@router.post(
    "/{review_id}/reflection",
    response_model=SuccessEnvelope[ReviewDetailRead],
    operation_id="reflect_on_next_day_review",
    summary="Teacher answers the reflective coaching question (T-202, #49)",
    dependencies=[require_role("teacher")],
)
async def reflect(
    review_id: str,
    payload: ReflectionCreate,
    claims: dict[str, Any] = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    detail = await NextDayReviewService(session).reflect(claims, review_id, payload.response)
    return success(detail.model_dump(mode="json"))
