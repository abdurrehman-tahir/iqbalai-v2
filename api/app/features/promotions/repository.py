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

    async def update(self, row: GradePromotionRequest) -> GradePromotionRequest:
        await self._session.commit()
        await self._session.refresh(row)
        return row

    async def list_for_school(
        self,
        school_id: str,
        *,
        status: GradePromotionRequestStatus | None = None,
    ) -> list[GradePromotionRequest]:
        stmt = select(GradePromotionRequest).where(
            GradePromotionRequest.school_id == school_id,
            not_deleted(GradePromotionRequest),
        )
        if status is not None:
            stmt = stmt.where(GradePromotionRequest.status == status)
        stmt = stmt.order_by(GradePromotionRequest.requested_at.desc())
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
