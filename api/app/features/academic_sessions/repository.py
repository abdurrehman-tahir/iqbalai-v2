"""Academic Session repository — all DB queries (T-042)."""

from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import not_deleted
from app.features.academic_sessions.models import AcademicSession
from app.features.schools.models import School


class AcademicSessionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_by_school(self, school_id: str) -> list[AcademicSession]:
        stmt = (
            select(AcademicSession)
            .where(AcademicSession.school_id == school_id, not_deleted(AcademicSession))
            .order_by(AcademicSession.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_id(self, id: str) -> AcademicSession | None:
        result = await self._session.execute(
            select(AcademicSession).where(AcademicSession.id == id)
        )
        return result.scalar_one_or_none()

    async def get_by_label(self, school_id: str, label: str) -> AcademicSession | None:
        result = await self._session.execute(
            select(AcademicSession).where(
                AcademicSession.school_id == school_id,
                AcademicSession.label == label,
                not_deleted(AcademicSession),
            )
        )
        return result.scalar_one_or_none()

    async def get_active(self, school_id: str) -> AcademicSession | None:
        result = await self._session.execute(
            select(AcademicSession).where(
                AcademicSession.school_id == school_id,
                AcademicSession.is_active.is_(True),
                not_deleted(AcademicSession),
            )
        )
        return result.scalar_one_or_none()

    async def create(self, session_row: AcademicSession) -> AcademicSession:
        self._session.add(session_row)
        await self._session.commit()
        await self._session.refresh(session_row)
        return session_row

    async def deactivate_all(self, school_id: str) -> None:
        await self._session.execute(
            update(AcademicSession)
            .where(
                AcademicSession.school_id == school_id,
                AcademicSession.is_active.is_(True),
                not_deleted(AcademicSession),
            )
            .values(is_active=False)
        )

    async def set_active(
        self, session_row: AcademicSession, school_id: str, label: str
    ) -> AcademicSession:
        await self.deactivate_all(school_id)
        session_row.is_active = True
        await self._session.execute(
            update(School).where(School.id == school_id).values(active_academic_session=label)
        )
        await self._session.commit()
        await self._session.refresh(session_row)
        return session_row

    async def get_school_active_label(self, school_id: str) -> str | None:
        result = await self._session.execute(
            select(School.active_academic_session).where(School.id == school_id)
        )
        return result.scalar_one_or_none()
