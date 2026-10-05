"""Lecture rating HTTP API — T-192."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db, require_role
from app.core.responses import SuccessEnvelope, success
from app.features.lecture_ratings.schemas import (
    LectureRatingSubmit,
    LectureRatingSummaryRead,
    MyLectureRatingRead,
)
from app.features.lecture_ratings.service import LectureRatingService

student_router = APIRouter(prefix="/students/me/lectures", tags=["student-lecture-rating"])
staff_router = APIRouter(prefix="/lectures", tags=["lecture-rating-summary"])


@student_router.get(
    "/{lecture_id}/rating",
    response_model=SuccessEnvelope[MyLectureRatingRead],
    operation_id="student_get_my_lecture_rating",
    summary="The caller's own rating for a lecture (null if not rated) (T-192)",
    dependencies=[require_role("student")],
)
async def get_my_lecture_rating(
    lecture_id: str,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    result = await LectureRatingService(db).get_mine(claims, lecture_id)
    return success(result.model_dump(mode="json"))


@student_router.put(
    "/{lecture_id}/rating",
    response_model=SuccessEnvelope[MyLectureRatingRead],
    operation_id="student_rate_lecture",
    summary="Submit or change an optional 1-5 rating after completing a lecture (T-192)",
    dependencies=[require_role("student")],
)
async def rate_lecture(
    lecture_id: str,
    payload: LectureRatingSubmit,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    result = await LectureRatingService(db).submit(claims, lecture_id, payload.rating)
    return success(result.model_dump(mode="json"))


@staff_router.get(
    "/{lecture_id}/rating-summary",
    response_model=SuccessEnvelope[LectureRatingSummaryRead],
    operation_id="lecture_rating_summary",
    summary="Anonymous rating aggregate + blended quality score (teacher/staff) (T-192)",
    dependencies=[require_role("teacher")],
)
async def lecture_rating_summary(
    lecture_id: str,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    result = await LectureRatingService(db).summary(claims, lecture_id)
    return success(result.model_dump(mode="json"))
