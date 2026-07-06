"""Graduation persistence — T-085/T-086."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import not_deleted
from app.features.graduation.models import (
    GraduationMigrationLog,
    GraduationMigrationStatus,
    GraduationRequest,
    GraduationRequestStatus,
)


class GraduationRequestRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, request_id: str) -> GraduationRequest | None:
        result = await self._session.execute(
            select(GraduationRequest).where(
                GraduationRequest.id == request_id,
                not_deleted(GraduationRequest),
            )
        )
        return result.scalar_one_or_none()

    async def get_pending_for_student(self, student_user_id: str) -> GraduationRequest | None:
        result = await self._session.execute(
            select(GraduationRequest).where(
                GraduationRequest.student_user_id == student_user_id,
                GraduationRequest.status == GraduationRequestStatus.PENDING,
                not_deleted(GraduationRequest),
            )
        )
        return result.scalar_one_or_none()

    async def list_for_school(self, school_id: str) -> list[GraduationRequest]:
        result = await self._session.execute(
            select(GraduationRequest)
            .where(
                GraduationRequest.school_id == school_id,
                not_deleted(GraduationRequest),
            )
            .order_by(GraduationRequest.requested_at.desc())
        )
        return list(result.scalars().all())

    async def create(self, request: GraduationRequest) -> GraduationRequest:
        self._session.add(request)
        await self._session.flush()
        return request

    async def update(self, request: GraduationRequest) -> GraduationRequest:
        await self._session.flush()
        return request


class GraduationMigrationLogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_student(self, student_user_id: str) -> GraduationMigrationLog | None:
        result = await self._session.execute(
            select(GraduationMigrationLog)
            .where(
                GraduationMigrationLog.student_user_id == student_user_id,
                not_deleted(GraduationMigrationLog),
            )
            .order_by(GraduationMigrationLog.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def list_due_for_migration(self, cutoff: datetime) -> list[GraduationMigrationLog]:
        result = await self._session.execute(
            select(GraduationMigrationLog).where(
                GraduationMigrationLog.migration_scheduled_at <= cutoff,
                GraduationMigrationLog.migration_status.in_(
                    [GraduationMigrationStatus.PENDING, GraduationMigrationStatus.FAILED]
                ),
                not_deleted(GraduationMigrationLog),
            )
        )
        return list(result.scalars().all())

    async def list_pending_reminders(self) -> list[GraduationMigrationLog]:
        result = await self._session.execute(
            select(GraduationMigrationLog).where(
                GraduationMigrationLog.migration_status == GraduationMigrationStatus.PENDING,
                not_deleted(GraduationMigrationLog),
            )
        )
        return list(result.scalars().all())

    async def create(self, log: GraduationMigrationLog) -> GraduationMigrationLog:
        self._session.add(log)
        await self._session.flush()
        return log

    async def update(self, log: GraduationMigrationLog) -> GraduationMigrationLog:
        await self._session.flush()
        return log
