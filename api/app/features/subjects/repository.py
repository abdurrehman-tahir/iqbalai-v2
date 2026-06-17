"""Subject repository — all DB queries for the subject catalogue (T-041).

Subjects are school-scoped (``school_id``); every query is filtered by the caller's
school at the service layer. Soft-deleted rows (``deleted_at IS NOT NULL``) are
excluded by default; archived rows (``status = 'archived'``) are excluded from the
default list but remain in the table.
"""

from __future__ import annotations

from datetime import datetime, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import not_deleted
from app.features.subjects.models import Subject, SubjectStatus

logger = structlog.get_logger(__name__)


class SubjectRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_by_school(self, school_id: str, include_archived: bool = False) -> list[Subject]:
        """Return a school's active (non-deleted) subjects, newest first.

        Archived subjects are hidden unless ``include_archived`` is set.
        """
        stmt = select(Subject).where(Subject.school_id == school_id, not_deleted(Subject))
        if not include_archived:
            stmt = stmt.where(Subject.status == SubjectStatus.ACTIVE)
        stmt = stmt.order_by(Subject.created_at.desc())
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_id(self, id: str) -> Subject | None:
        result = await self._session.execute(select(Subject).where(Subject.id == id))
        return result.scalar_one_or_none()

    async def get_active_by_name(self, school_id: str, name: str) -> Subject | None:
        """Return a non-deleted subject with this exact name in the school, if any."""
        result = await self._session.execute(
            select(Subject).where(
                Subject.school_id == school_id,
                Subject.name == name,
                not_deleted(Subject),
            )
        )
        return result.scalar_one_or_none()

    async def create(self, subject: Subject) -> Subject:
        self._session.add(subject)
        await self._session.commit()
        await self._session.refresh(subject)
        return subject

    async def update(self, subject: Subject) -> Subject:
        await self._session.commit()
        await self._session.refresh(subject)
        return subject

    async def soft_delete(self, subject: Subject) -> None:
        subject.deleted_at = datetime.now(timezone.utc)
        await self._session.commit()
