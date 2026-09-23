"""Student lecture viewer — published text mode (T-152, Flow 6 §3.2 / #54).

Opens a T-151 study session as part of the viewer open path. Independent
self-study is out of scope (Flow 8).
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, PermissionDeniedError
from app.db.base import not_deleted
from app.features.lectures.lecture_session import LectureSessionService
from app.features.lectures.models import LectureStatus, SchoolLecture, SchoolLectureParagraph
from app.features.lectures.repository import LectureParagraphRepository, LectureRepository
from app.features.lectures.schemas import (
    LectureSessionOpenRequest,
    ParagraphSourceMetadata,
    StudentLectureCardRead,
    StudentLectureParagraphRead,
    StudentLectureViewerRead,
)
from app.features.lectures.service import LectureService
from app.features.users.models import User, UserRole
from app.features.users.repository import UserRepository


class StudentLectureViewerService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._users = UserRepository(session)
        self._lectures = LectureRepository(session)
        self._paragraphs = LectureParagraphRepository(session)
        self._lecture_svc = LectureService(session)
        self._sessions = LectureSessionService(session)

    async def _require_student(self, claims: dict[str, object]) -> User:
        user = await self._users.get_by_authentik_id(str(claims.get("sub", "")))
        if user is None or user.deleted_at is not None:
            raise NotFoundError("User profile not found")
        if user.role != UserRole.STUDENT:
            raise PermissionDeniedError("Student role required")
        return user

    async def list_my_lectures(self, claims: dict[str, object]) -> list[StudentLectureCardRead]:
        """Published lectures the student can access (dashboard entry points)."""
        student = await self._require_student(claims)
        rows = (
            (
                await self._session.execute(
                    select(SchoolLecture)
                    .where(
                        not_deleted(SchoolLecture),
                        SchoolLecture.status == LectureStatus.PUBLISHED,
                        SchoolLecture.current_version_id.is_not(None),
                        SchoolLecture.school_id == student.school_id,
                    )
                    .order_by(SchoolLecture.updated_at.desc())
                )
            )
            .scalars()
            .all()
        )

        cards: list[StudentLectureCardRead] = []
        for lecture in rows:
            if not await self._lecture_svc.student_can_access_lecture(student, lecture):
                continue
            assert lecture.current_version_id is not None
            cards.append(
                StudentLectureCardRead(
                    lecture_id=lecture.id,
                    title=lecture.title,
                    topic=lecture.topic,
                    current_version_id=lecture.current_version_id,
                )
            )
        return cards

    async def open_viewer(
        self,
        claims: dict[str, object],
        lecture_id: str,
        *,
        mode_payload: LectureSessionOpenRequest | None = None,
    ) -> StudentLectureViewerRead:
        """Open viewer: enforce access, start T-151 session, return current published text."""
        student = await self._require_student(claims)
        lecture = await self._lectures.get_by_id(lecture_id)
        if lecture is None or lecture.status != LectureStatus.PUBLISHED:
            raise NotFoundError("Lecture not found")
        if lecture.current_version_id is None:
            raise NotFoundError("Lecture has no published version")
        if not await self._lecture_svc.student_can_access_lecture(student, lecture):
            raise PermissionDeniedError("Not enrolled or access-restricted for this lecture")

        session_read = await self._sessions.open_session(
            claims, lecture_id, mode_payload or LectureSessionOpenRequest()
        )

        paragraphs = await self._paragraphs.list_by_version(lecture.current_version_id)
        return StudentLectureViewerRead(
            lecture_id=lecture.id,
            title=lecture.title,
            topic=lecture.topic,
            current_version_id=lecture.current_version_id,
            language=None,
            paragraphs=[_paragraph_to_read(p) for p in paragraphs],
            session=session_read,
        )


def _paragraph_to_read(paragraph: SchoolLectureParagraph) -> StudentLectureParagraphRead:
    meta = ParagraphSourceMetadata.from_jsonb(paragraph.source_metadata_jsonb)
    return StudentLectureParagraphRead(
        id=paragraph.id,
        ordinal=paragraph.ordinal,
        text=paragraph.text,
        tier=meta.tier,
        book_name=meta.book_name,
        source_url=meta.source_url,
    )
