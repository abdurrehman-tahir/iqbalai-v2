"""Promotion request repository — T-251."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import not_deleted
from app.features.promotions.models import GradePromotionRequest, GradePromotionRequestStatus


class GradePromotionRequestRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, request_id: str) -> GradePromotionRequest | None:
        result = await self._session.execute(
            select(GradePromotionRequest).where(
                GradePromotionRequest.id == request_id,
                not_deleted(GradePromotionRequest),
            )
        )
        return result.scalar_one_or_none()

    async def get_pending_for_grade(self, grade_id: str) -> GradePromotionRequest | None:
        result = await self._session.execute(
            select(GradePromotionRequest).where(
                GradePromotionRequest.initiating_grade_id == grade_id,
                GradePromotionRequest.status == GradePromotionRequestStatus.PENDING_APPROVAL,
                not_deleted(GradePromotionRequest),
            )
        )
        return result.scalar_one_or_none()

    async def create(self, row: GradePromotionRequest) -> GradePromotionRequest:
        self._session.add(row)
        await self._session.commit()
        await self._session.refresh(row)
        return row
