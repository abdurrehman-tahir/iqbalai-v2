"""Exam Syllabi repository — all DB queries for syllabi and topics."""

from __future__ import annotations

from datetime import datetime, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import not_deleted
from app.features.exam_syllabi.models import ExamSyllabus, SyllabusTopic

logger = structlog.get_logger(__name__)


class ExamSyllabiRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ── Syllabi ───────────────────────────────────────────────────────────────

    async def list_syllabi(self) -> list[ExamSyllabus]:
        """Return all active (non-deleted) syllabi."""
        result = await self._session.execute(select(ExamSyllabus).where(not_deleted(ExamSyllabus)))
        return list(result.scalars().all())

    async def get_by_id(self, id: str) -> ExamSyllabus | None:
        result = await self._session.execute(select(ExamSyllabus).where(ExamSyllabus.id == id))
        return result.scalar_one_or_none()

    async def create(self, syllabus: ExamSyllabus) -> ExamSyllabus:
        self._session.add(syllabus)
        await self._session.commit()
        await self._session.refresh(syllabus)
        return syllabus

    async def update(self, syllabus: ExamSyllabus) -> ExamSyllabus:
        await self._session.commit()
        await self._session.refresh(syllabus)
        return syllabus

    async def soft_delete(self, syllabus: ExamSyllabus) -> None:
        syllabus.deleted_at = datetime.now(timezone.utc)
        await self._session.commit()

    # ── Topics ────────────────────────────────────────────────────────────────

    async def list_topics(self, syllabus_id: str) -> list[SyllabusTopic]:
        """Return non-deleted topics for a syllabus, ordered by depth then order_index."""
        result = await self._session.execute(
            select(SyllabusTopic)
            .where(
                SyllabusTopic.syllabus_id == syllabus_id,
                not_deleted(SyllabusTopic),
            )
            .order_by(SyllabusTopic.depth, SyllabusTopic.order_index)
        )
        return list(result.scalars().all())

    async def get_topic_by_id(self, id: str) -> SyllabusTopic | None:
        result = await self._session.execute(select(SyllabusTopic).where(SyllabusTopic.id == id))
        return result.scalar_one_or_none()

    async def create_topic(self, topic: SyllabusTopic) -> SyllabusTopic:
        self._session.add(topic)
        await self._session.commit()
        await self._session.refresh(topic)
        return topic

    async def soft_delete_topic(self, topic: SyllabusTopic) -> None:
        topic.deleted_at = datetime.now(timezone.utc)
        await self._session.commit()
