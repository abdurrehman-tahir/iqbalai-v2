"""Lecture draft + lecture row repository — school schema (T-114/T-115)."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import not_deleted
from app.features.lectures.models import (
    SchoolLecture,
    SchoolLectureDraft,
    SchoolLectureParagraph,
    SchoolLectureVoiceSession,
    SchoolLectureVoiceTurn,
    VoiceSessionStatus,
)


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


class LectureParagraphRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_by_version(self, lecture_version_id: str) -> list[SchoolLectureParagraph]:
        result = await self._session.execute(
            select(SchoolLectureParagraph)
            .where(SchoolLectureParagraph.lecture_version_id == lecture_version_id)
            .order_by(SchoolLectureParagraph.ordinal.asc())
        )
        return list(result.scalars().all())


class LectureVoiceSessionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, session_id: str) -> SchoolLectureVoiceSession | None:
        return await self._session.get(SchoolLectureVoiceSession, session_id)

    async def get_active_for_teacher_and_lecture(
        self, *, teacher_user_id: str, lecture_id: str
    ) -> SchoolLectureVoiceSession | None:
        """Enforces "single active session per teacher per lecture" (flow-5 §5.4)."""
        result = await self._session.execute(
            select(SchoolLectureVoiceSession).where(
                SchoolLectureVoiceSession.teacher_user_id == teacher_user_id,
                SchoolLectureVoiceSession.lecture_id == lecture_id,
                SchoolLectureVoiceSession.status == VoiceSessionStatus.ACTIVE,
            )
        )
        return result.scalar_one_or_none()

    async def create(self, voice_session: SchoolLectureVoiceSession) -> SchoolLectureVoiceSession:
        self._session.add(voice_session)
        await self._session.commit()
        await self._session.refresh(voice_session)
        return voice_session

    async def end(self, voice_session: SchoolLectureVoiceSession) -> SchoolLectureVoiceSession:
        voice_session.status = VoiceSessionStatus.ENDED
        voice_session.ended_at = datetime.now(timezone.utc)
        await self._session.commit()
        await self._session.refresh(voice_session)
        return voice_session

    async def end_all_active_for_teacher(self, teacher_user_id: str) -> None:
        """Terminates a suspended teacher's sessions (flow-5 §5.4 edge case)."""
        result = await self._session.execute(
            select(SchoolLectureVoiceSession).where(
                SchoolLectureVoiceSession.teacher_user_id == teacher_user_id,
                SchoolLectureVoiceSession.status == VoiceSessionStatus.ACTIVE,
            )
        )
        for voice_session in result.scalars().all():
            voice_session.status = VoiceSessionStatus.ENDED
            voice_session.ended_at = datetime.now(timezone.utc)
        await self._session.commit()


class LectureVoiceTurnRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_by_session(self, session_id: str) -> list[SchoolLectureVoiceTurn]:
        result = await self._session.execute(
            select(SchoolLectureVoiceTurn)
            .where(SchoolLectureVoiceTurn.session_id == session_id)
            .order_by(SchoolLectureVoiceTurn.ordinal.asc())
        )
        return list(result.scalars().all())

    async def count_for_session(self, session_id: str) -> int:
        turns = await self.list_by_session(session_id)
        return len(turns)

    async def create(self, turn: SchoolLectureVoiceTurn) -> SchoolLectureVoiceTurn:
        self._session.add(turn)
        await self._session.commit()
        await self._session.refresh(turn)
        return turn

    async def list_with_unpurged_audio_older_than(
        self, cutoff: datetime
    ) -> list[SchoolLectureVoiceTurn]:
        """Turns whose raw audio has passed the retention window (T-121 #25)."""
        result = await self._session.execute(
            select(SchoolLectureVoiceTurn).where(
                SchoolLectureVoiceTurn.audio_storage_key.is_not(None),
                SchoolLectureVoiceTurn.audio_purged_at.is_(None),
                SchoolLectureVoiceTurn.created_at < cutoff,
            )
        )
        return list(result.scalars().all())

    async def mark_audio_purged(self, turn: SchoolLectureVoiceTurn) -> None:
        turn.audio_storage_key = None
        turn.audio_purged_at = datetime.now(timezone.utc)
        await self._session.commit()
