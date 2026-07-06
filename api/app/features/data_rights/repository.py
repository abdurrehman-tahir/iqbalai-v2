"""Data rights request persistence — T-084."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import not_deleted
from app.features.data_rights.models import (
    DataRightsRequest,
    DataRightsRequestStatus,
    DataRightsRequestType,
)


class DataRightsRequestRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, request_id: str) -> DataRightsRequest | None:
        result = await self._session.execute(
            select(DataRightsRequest).where(
                DataRightsRequest.id == request_id,
                not_deleted(DataRightsRequest),
            )
        )
        return result.scalar_one_or_none()

    async def get_for_user(self, *, request_id: str, user_id: str) -> DataRightsRequest | None:
        result = await self._session.execute(
            select(DataRightsRequest).where(
                DataRightsRequest.id == request_id,
                DataRightsRequest.user_id == user_id,
                not_deleted(DataRightsRequest),
            )
        )
        return result.scalar_one_or_none()

    async def list_for_user(self, user_id: str) -> list[DataRightsRequest]:
        result = await self._session.execute(
            select(DataRightsRequest)
            .where(
                DataRightsRequest.user_id == user_id,
                not_deleted(DataRightsRequest),
            )
            .order_by(DataRightsRequest.requested_at.desc())
        )
        return list(result.scalars().all())

    async def get_active_export(self, user_id: str) -> DataRightsRequest | None:
        result = await self._session.execute(
            select(DataRightsRequest).where(
                DataRightsRequest.user_id == user_id,
                DataRightsRequest.request_type == DataRightsRequestType.EXPORT,
                DataRightsRequest.status.in_(
                    [
                        DataRightsRequestStatus.REQUESTED,
                        DataRightsRequestStatus.PROCESSING,
                        DataRightsRequestStatus.READY,
                    ]
                ),
                not_deleted(DataRightsRequest),
            )
        )
        return result.scalar_one_or_none()

    async def get_active_deletion(self, user_id: str) -> DataRightsRequest | None:
        result = await self._session.execute(
            select(DataRightsRequest).where(
                DataRightsRequest.user_id == user_id,
                DataRightsRequest.request_type == DataRightsRequestType.DELETION,
                DataRightsRequest.status == DataRightsRequestStatus.GRACE_PERIOD,
                not_deleted(DataRightsRequest),
            )
        )
        return result.scalar_one_or_none()

    async def create(self, request: DataRightsRequest) -> DataRightsRequest:
        self._session.add(request)
        await self._session.flush()
        return request

    async def update(self, request: DataRightsRequest) -> DataRightsRequest:
        await self._session.flush()
        return request
