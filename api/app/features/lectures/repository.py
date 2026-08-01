"""Lecture draft + lecture row repository — school schema (T-114/T-115)."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import not_deleted
from app.features.lectures.models import SchoolLecture, SchoolLectureDraft


class LectureDraftRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_active_for_teacher(self, teacher_user_id: str) -> SchoolLectureDraft | None:
        result = await self._session.execute(
            select(SchoolLectureDraft).where(
                SchoolLectureDraft.teacher_user_id == teacher_user_id,
                not_deleted(SchoolLectureDraft),
            )
        )
        return result.scalar_one_or_none()

    async def create(self, draft: SchoolLectureDraft) -> SchoolLectureDraft:
        self._session.add(draft)
        await self._session.commit()
        await self._session.refresh(draft)
        return draft

    async def update(self, draft: SchoolLectureDraft) -> SchoolLectureDraft:
        await self._session.commit()
        await self._session.refresh(draft)
        return draft

    async def soft_delete(self, draft: SchoolLectureDraft) -> None:
        draft.deleted_at = datetime.now(timezone.utc)
        await self._session.commit()


class LectureRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, lecture: SchoolLecture) -> SchoolLecture:
        self._session.add(lecture)
        await self._session.commit()
        await self._session.refresh(lecture)
        return lecture

    async def get_by_id(self, lecture_id: str) -> SchoolLecture | None:
        return await self._session.get(SchoolLecture, lecture_id)
