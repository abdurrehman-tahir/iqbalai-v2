"""Lecture draft + lecture row repository — independent schema (T-125).

Mirrors ``repository.py``'s school-schema classes field-for-field, scoped to
the ``Independent*`` model classes (this codebase routes schemas via
separate ORM classes per tenant, not a runtime schema_translate_map — see
``independent_teacher_onboarding`` for the same pattern).
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import not_deleted
from app.features.lectures.models import (
    IndependentLecture,
    IndependentLectureDraft,
    IndependentLectureParagraph,
    IndependentLectureVersion,
    IndependentLectureVoiceSession,
    IndependentLectureVoiceTurn,
    VoiceSessionStatus,
)


class IndependentLectureDraftRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_active_for_teacher(self, teacher_user_id: str) -> IndependentLectureDraft | None:
        result = await self._session.execute(
            select(IndependentLectureDraft).where(
                IndependentLectureDraft.teacher_user_id == teacher_user_id,
                not_deleted(IndependentLectureDraft),
            )
        )
        return result.scalar_one_or_none()

    async def create(self, draft: IndependentLectureDraft) -> IndependentLectureDraft:
        self._session.add(draft)
        await self._session.commit()
        await self._session.refresh(draft)
        return draft

    async def update(self, draft: IndependentLectureDraft) -> IndependentLectureDraft:
        await self._session.commit()
        await self._session.refresh(draft)
        return draft

    async def soft_delete(self, draft: IndependentLectureDraft) -> None:
        draft.deleted_at = datetime.now(timezone.utc)
        await self._session.commit()


class IndependentLectureRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, lecture: IndependentLecture) -> IndependentLecture:
        self._session.add(lecture)
        await self._session.commit()
        await self._session.refresh(lecture)
        return lecture

    async def get_by_id(self, lecture_id: str) -> IndependentLecture | None:
        return await self._session.get(IndependentLecture, lecture_id)


class IndependentLectureVersionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, version_id: str) -> IndependentLectureVersion | None:
        return await self._session.get(IndependentLectureVersion, version_id)


class IndependentLectureParagraphRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_by_version(self, lecture_version_id: str) -> list[IndependentLectureParagraph]:
        result = await self._session.execute(
            select(IndependentLectureParagraph)
            .where(IndependentLectureParagraph.lecture_version_id == lecture_version_id)
            .order_by(IndependentLectureParagraph.ordinal.asc())
        )
        return list(result.scalars().all())


class IndependentLectureVoiceSessionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, session_id: str) -> IndependentLectureVoiceSession | None:
        return await self._session.get(IndependentLectureVoiceSession, session_id)

    async def get_active_for_teacher_and_lecture(
        self, *, teacher_user_id: str, lecture_id: str
    ) -> IndependentLectureVoiceSession | None:
        result = await self._session.execute(
            select(IndependentLectureVoiceSession).where(
                IndependentLectureVoiceSession.teacher_user_id == teacher_user_id,
                IndependentLectureVoiceSession.lecture_id == lecture_id,
                IndependentLectureVoiceSession.status == VoiceSessionStatus.ACTIVE,
            )
        )
        return result.scalar_one_or_none()

    async def create(
        self, voice_session: IndependentLectureVoiceSession
    ) -> IndependentLectureVoiceSession:
        self._session.add(voice_session)
        await self._session.commit()
        await self._session.refresh(voice_session)
        return voice_session

    async def end(
        self, voice_session: IndependentLectureVoiceSession
    ) -> IndependentLectureVoiceSession:
        voice_session.status = VoiceSessionStatus.ENDED
        voice_session.ended_at = datetime.now(timezone.utc)
        await self._session.commit()
        await self._session.refresh(voice_session)
        return voice_session


class IndependentLectureVoiceTurnRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_by_session(self, session_id: str) -> list[IndependentLectureVoiceTurn]:
        result = await self._session.execute(
            select(IndependentLectureVoiceTurn)
            .where(IndependentLectureVoiceTurn.session_id == session_id)
            .order_by(IndependentLectureVoiceTurn.ordinal.asc())
        )
        return list(result.scalars().all())

    async def count_for_session(self, session_id: str) -> int:
        turns = await self.list_by_session(session_id)
        return len(turns)

    async def create(self, turn: IndependentLectureVoiceTurn) -> IndependentLectureVoiceTurn:
        self._session.add(turn)
        await self._session.commit()
        await self._session.refresh(turn)
        return turn

    async def list_with_unpurged_audio_older_than(
        self, cutoff: datetime
    ) -> list[IndependentLectureVoiceTurn]:
        """Turns whose raw audio has passed the retention window (T-121 pattern)."""
        result = await self._session.execute(
            select(IndependentLectureVoiceTurn).where(
                IndependentLectureVoiceTurn.audio_storage_key.is_not(None),
                IndependentLectureVoiceTurn.audio_purged_at.is_(None),
                IndependentLectureVoiceTurn.created_at < cutoff,
            )
        )
        return list(result.scalars().all())

    async def mark_audio_purged(self, turn: IndependentLectureVoiceTurn) -> None:
        turn.audio_storage_key = None
        turn.audio_purged_at = datetime.now(timezone.utc)
        await self._session.commit()
