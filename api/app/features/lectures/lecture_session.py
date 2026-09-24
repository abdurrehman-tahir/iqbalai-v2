"""Student lecture study session lifecycle (T-151 / T-163, Flow 6 §3.1).

Opens a NEW session on every lecture open. Concurrent active sessions for the
same student+lecture are allowed (distinct devices). Sessions end on explicit
close or after 30 minutes of inactivity (lazy check + Celery beat sweep).

T-163: emits ``student.lecture.session_opened`` / ``student.lecture.session_closed``
(with session summary) onto NATS — emit-only; consumers are M-14 / Flow 9.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, PermissionDeniedError, ValidationError
from app.core.tenant import get_tenant_type
from app.features.lectures.events import publish_session_closed, publish_session_opened
from app.features.lectures.models import (
    LectureSessionMode,
    LectureSessionStatus,
    LectureStatus,
    LectureTenantType,
    SchoolLecture,
    SchoolLectureSession,
)
from app.features.lectures.repository import LectureRepository, LectureSessionRepository
from app.features.lectures.schemas import (
    LectureSessionModeLiteral,
    LectureSessionModeUpdateRequest,
    LectureSessionOpenRequest,
    LectureSessionRead,
    LectureSessionStatusLiteral,
)
from app.features.lectures.service import LectureService
from app.features.student_questions.repository import StudentQuestionRepository
from app.features.users.models import User, UserRole
from app.features.users.repository import UserRepository

INACTIVITY_TIMEOUT = timedelta(minutes=30)

EndReason = Literal["explicit", "inactivity"]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _to_read(row: SchoolLectureSession) -> LectureSessionRead:
    return LectureSessionRead(
        id=row.id,
        lecture_id=row.lecture_id,
        student_user_id=row.student_user_id,
        tenant_type=row.tenant_type.value,
        mode=LectureSessionModeLiteral(row.mode.value),
        status=LectureSessionStatusLiteral(row.status.value),
        opened_at=row.opened_at,
        last_activity_at=row.last_activity_at,
        ended_at=row.ended_at,
    )


def _duration_seconds(row: SchoolLectureSession) -> int:
    end = row.ended_at or row.last_activity_at
    if end is None or row.opened_at is None:
        return 0
    return max(0, int((end - row.opened_at).total_seconds()))


def _tenant_type_from_claims(claims: dict[str, object]) -> LectureTenantType:
    """Open Q13 — tag independent sessions when claims say independent."""
    if get_tenant_type(claims) == "independent":
        return LectureTenantType.INDEPENDENT
    return LectureTenantType.SCHOOL


class LectureSessionService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._users = UserRepository(session)
        self._lectures = LectureRepository(session)
        self._sessions = LectureSessionRepository(session)
        self._lecture_svc = LectureService(session)
        self._questions = StudentQuestionRepository(session)

    async def _require_student(self, claims: dict[str, object]) -> User:
        user = await self._users.get_by_authentik_id(str(claims.get("sub", "")))
        if user is None or user.deleted_at is not None:
            raise NotFoundError("User profile not found")
        if user.role != UserRole.STUDENT:
            raise PermissionDeniedError("Student role required")
        return user

    async def _require_published_accessible(self, student: User, lecture_id: str) -> SchoolLecture:
        lecture = await self._lectures.get_by_id(lecture_id)
        if lecture is None:
            raise NotFoundError("Lecture not found")
        if lecture.status != LectureStatus.PUBLISHED:
            raise NotFoundError("Lecture not found")
        if not await self._lecture_svc.student_can_access_lecture(student, lecture):
            raise PermissionDeniedError("Not enrolled or access-restricted for this lecture")
        return lecture

    async def _resolve_school_id(self, row: SchoolLectureSession) -> str:
        lecture = await self._lectures.get_by_id(row.lecture_id)
        if lecture is not None and lecture.school_id:
            return lecture.school_id
        user = await self._users.get_by_id(row.student_user_id)
        return (user.school_id if user and user.school_id else "") or ""

    async def _build_session_summary(
        self,
        row: SchoolLectureSession,
        *,
        end_reason: EndReason,
        school_id: str | None = None,
    ) -> dict[str, object]:
        resolved_school = school_id if school_id is not None else await self._resolve_school_id(row)
        question_count = await self._questions.count_for_session(row.id)
        highlight_count = await self._questions.count_highlights_for_session(row.id)
        return {
            "session_id": row.id,
            "lecture_id": row.lecture_id,
            "student_user_id": row.student_user_id,
            "school_id": resolved_school,
            "tenant_type": row.tenant_type.value,
            "mode": row.mode.value,
            "opened_at": row.opened_at.isoformat() if row.opened_at else None,
            "ended_at": row.ended_at.isoformat() if row.ended_at else None,
            "last_activity_at": row.last_activity_at.isoformat() if row.last_activity_at else None,
            "duration_seconds": _duration_seconds(row),
            "question_count": question_count,
            "highlight_count": highlight_count,
            "end_reason": end_reason,
        }

    async def _emit_session_closed(
        self,
        row: SchoolLectureSession,
        *,
        end_reason: EndReason,
        school_id: str | None = None,
    ) -> None:
        summary = await self._build_session_summary(row, end_reason=end_reason, school_id=school_id)
        await publish_session_closed(payload=summary)

    def _is_stale(self, row: SchoolLectureSession, *, now: datetime | None = None) -> bool:
        if row.status != LectureSessionStatus.ACTIVE:
            return False
        clock = now or _utcnow()
        return row.last_activity_at < clock - INACTIVITY_TIMEOUT

    async def _end_if_stale(
        self, row: SchoolLectureSession, *, now: datetime | None = None
    ) -> SchoolLectureSession:
        clock = now or _utcnow()
        if not self._is_stale(row, now=clock):
            return row
        row.status = LectureSessionStatus.ENDED
        row.ended_at = clock
        saved = await self._sessions.save(row)
        await self._emit_session_closed(saved, end_reason="inactivity")
        return saved

    async def open_session(
        self, claims: dict[str, object], lecture_id: str, payload: LectureSessionOpenRequest
    ) -> LectureSessionRead:
        """Always creates a NEW active session (never resumes a timed-out one)."""
        student = await self._require_student(claims)
        lecture = await self._require_published_accessible(student, lecture_id)

        now = _utcnow()
        # Lazy sweep for stale sessions before opening; emit closed summaries.
        ended_rows = await self._sessions.end_stale_active(now - INACTIVITY_TIMEOUT, ended_at=now)
        for ended in ended_rows:
            await self._emit_session_closed(ended, end_reason="inactivity")

        row = SchoolLectureSession(
            lecture_id=lecture_id,
            student_user_id=student.id,
            tenant_type=_tenant_type_from_claims(claims),
            mode=LectureSessionMode(payload.mode.value),
            status=LectureSessionStatus.ACTIVE,
            opened_at=now,
            last_activity_at=now,
            ended_at=None,
        )
        created = await self._sessions.create(row)
        await publish_session_opened(
            payload={
                "session_id": created.id,
                "lecture_id": created.lecture_id,
                "student_user_id": created.student_user_id,
                "school_id": lecture.school_id or "",
                "tenant_type": created.tenant_type.value,
                "mode": created.mode.value,
                "opened_at": created.opened_at.isoformat(),
            }
        )
        return _to_read(created)

    async def _require_owned_session(self, student: User, session_id: str) -> SchoolLectureSession:
        row = await self._sessions.get_by_id(session_id)
        if row is None or row.student_user_id != student.id:
            raise NotFoundError("Lecture session not found")
        return row

    async def get_session(self, claims: dict[str, object], session_id: str) -> LectureSessionRead:
        student = await self._require_student(claims)
        row = await self._require_owned_session(student, session_id)
        row = await self._end_if_stale(row)
        return _to_read(row)

    async def touch_activity(
        self, claims: dict[str, object], session_id: str
    ) -> LectureSessionRead:
        student = await self._require_student(claims)
        row = await self._require_owned_session(student, session_id)
        now = _utcnow()
        row = await self._end_if_stale(row, now=now)
        if row.status != LectureSessionStatus.ACTIVE:
            raise ValidationError("Lecture session has ended; open a new session")
        row.last_activity_at = now
        return _to_read(await self._sessions.save(row))

    async def set_mode(
        self,
        claims: dict[str, object],
        session_id: str,
        payload: LectureSessionModeUpdateRequest,
    ) -> LectureSessionRead:
        student = await self._require_student(claims)
        row = await self._require_owned_session(student, session_id)
        now = _utcnow()
        row = await self._end_if_stale(row, now=now)
        if row.status != LectureSessionStatus.ACTIVE:
            raise ValidationError("Lecture session has ended; open a new session")
        row.mode = LectureSessionMode(payload.mode.value)
        row.last_activity_at = now
        return _to_read(await self._sessions.save(row))

    async def end_session(self, claims: dict[str, object], session_id: str) -> LectureSessionRead:
        student = await self._require_student(claims)
        row = await self._require_owned_session(student, session_id)
        if row.status == LectureSessionStatus.ENDED:
            return _to_read(row)
        now = _utcnow()
        row.status = LectureSessionStatus.ENDED
        row.ended_at = now
        row.last_activity_at = now
        saved = await self._sessions.save(row)
        await self._emit_session_closed(
            saved,
            end_reason="explicit",
            school_id=student.school_id or "",
        )
        return _to_read(saved)


async def end_inactive_lecture_sessions(session: AsyncSession) -> dict[str, object]:
    """Celery beat entrypoint — end school sessions past the inactivity window."""
    now = _utcnow()
    cutoff = now - INACTIVITY_TIMEOUT
    svc = LectureSessionService(session)
    ended_rows = await LectureSessionRepository(session).end_stale_active(cutoff, ended_at=now)
    for row in ended_rows:
        await svc._emit_session_closed(row, end_reason="inactivity")
    return {"ended_count": len(ended_rows), "cutoff": cutoff.isoformat()}
