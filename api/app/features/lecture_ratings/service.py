"""Lecture rating service — T-192 (flow-6 §3.11: coaching, never grading).

- Students: submit/update their OWN optional 1–5 rating on a lecture they can
  access; read back only their own rating. Submissions are audit-logged.
- Teacher (own lecture) / Coordinator & School Admin (own school) / District
  Admin (own district) / Platform Admin: anonymous aggregate only — count +
  average, the average withheld below MIN_RATINGS_FOR_DISPLAY. The displayed
  quality score blends it at 5% into the M-10 AI score (95%).
- Ratings are never exposed per student and never used to rank students.
"""

from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, PermissionDeniedError
from app.features.audit.actions import LECTURE_RATING_SUBMITTED
from app.features.lecture_ratings.models import SchoolLectureRating
from app.features.lecture_ratings.repository import LectureRatingRepository
from app.features.lecture_ratings.schemas import LectureRatingSummaryRead, MyLectureRatingRead
from app.features.lectures.models import SchoolLecture
from app.features.lectures.repository import LectureRepository, LectureVersionRepository
from app.features.lectures.scoring import (
    MAX_TOTAL_SCORE,
    STUDENT_RATING_WEIGHT,
    blended_quality_score,
)
from app.features.lectures.service import LectureService
from app.features.schools.models import School
from app.features.users.models import User, UserRole
from app.features.users.repository import UserRepository
from app.infrastructure.audit.log import audit

# Anonymity guard: with fewer ratings the "average" would reveal individuals.
MIN_RATINGS_FOR_DISPLAY = 3

_STAFF_ROLES = (
    UserRole.COORDINATOR,
    UserRole.SCHOOL_ADMIN,
    UserRole.DISTRICT_ADMIN,
    UserRole.PLATFORM_ADMIN,
)


class LectureRatingService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._users = UserRepository(session)
        self._lectures = LectureRepository(session)
        self._versions = LectureVersionRepository(session)
        self._lecture_svc = LectureService(session)
        self._ratings = LectureRatingRepository(session)

    async def _require_user(self, claims: dict[str, object]) -> User:
        user = await self._users.get_by_authentik_id(str(claims.get("sub", "")))
        if user is None or user.deleted_at is not None:
            raise NotFoundError("User profile not found")
        return user

    async def _require_student_lecture(
        self, claims: dict[str, object], lecture_id: str
    ) -> tuple[User, SchoolLecture]:
        user = await self._require_user(claims)
        if user.role != UserRole.STUDENT:
            raise PermissionDeniedError("Student role required")
        lecture = await self._lectures.get_by_id(lecture_id)
        if lecture is None:
            raise NotFoundError("Lecture not found")
        if not await self._lecture_svc.student_can_access_lecture(user, lecture):
            raise PermissionDeniedError("Not enrolled or access-restricted for this lecture")
        return user, lecture

    async def get_mine(self, claims: dict[str, object], lecture_id: str) -> MyLectureRatingRead:
        student, _ = await self._require_student_lecture(claims, lecture_id)
        row = await self._ratings.get_own(lecture_id=lecture_id, student_user_id=student.id)
        return MyLectureRatingRead(lecture_id=lecture_id, rating=row.rating if row else None)

    async def submit(
        self, claims: dict[str, object], lecture_id: str, rating: int
    ) -> MyLectureRatingRead:
        student, lecture = await self._require_student_lecture(claims, lecture_id)
        row = await self._ratings.get_own(lecture_id=lecture_id, student_user_id=student.id)
        if row is None:
            row = SchoolLectureRating(
                lecture_id=lecture_id,
                student_user_id=student.id,
                lecture_version_id=lecture.current_version_id,
                rating=rating,
            )
            try:
                async with self._session.begin_nested():
                    self._session.add(row)
                    await self._session.flush()
            except IntegrityError:
                existing = await self._ratings.get_own(
                    lecture_id=lecture_id, student_user_id=student.id
                )
                if existing is None:
                    raise
                row = existing
                row.rating = rating
        else:
            row.rating = rating
            row.lecture_version_id = lecture.current_version_id
        await self._session.commit()
        # The audit row records THAT a rating happened — the value stays out of
        # the log so the audit trail can't be used to de-anonymise ratings.
        await audit(
            session=self._session,
            action=LECTURE_RATING_SUBMITTED,
            actor_id=student.id,
            actor_role=student.role.value,
            target_type="lecture",
            target_id=lecture_id,
            school_id=lecture.school_id,
        )
        return MyLectureRatingRead(lecture_id=lecture_id, rating=rating)

    async def summary(self, claims: dict[str, object], lecture_id: str) -> LectureRatingSummaryRead:
        user = await self._require_user(claims)
        lecture = await self._lectures.get_by_id(lecture_id)
        if lecture is None:
            raise NotFoundError("Lecture not found")
        await self._authorize_staff(user, lecture)

        count, average = await self._ratings.aggregate(lecture_id)
        shown_average = (
            round(average, 2) if average is not None and count >= MIN_RATINGS_FOR_DISPLAY else None
        )
        ai_total = await self._ai_total(lecture)
        return LectureRatingSummaryRead(
            lecture_id=lecture_id,
            rating_count=count,
            min_ratings_for_display=MIN_RATINGS_FOR_DISPLAY,
            average_rating=shown_average,
            ai_score=ai_total,
            ai_score_max=MAX_TOTAL_SCORE,
            quality_score=blended_quality_score(ai_total, shown_average),
            rating_weight=STUDENT_RATING_WEIGHT,
        )

    async def _authorize_staff(self, user: User, lecture: SchoolLecture) -> None:
        if user.role == UserRole.TEACHER:
            if lecture.teacher_user_id != user.id or lecture.school_id != user.school_id:
                raise NotFoundError("Lecture not found")
            return
        if user.role not in _STAFF_ROLES:
            raise PermissionDeniedError("Teacher, Coordinator or Admin role required")
        if user.role in (UserRole.COORDINATOR, UserRole.SCHOOL_ADMIN):
            if lecture.school_id is None or lecture.school_id != user.school_id:
                raise NotFoundError("Lecture not found")
        elif user.role == UserRole.DISTRICT_ADMIN:
            school = (
                await self._session.get(School, lecture.school_id) if lecture.school_id else None
            )
            if school is None or school.district_id != user.district_id:
                raise NotFoundError("Lecture not found")

    async def _ai_total(self, lecture: SchoolLecture) -> int | None:
        version = (
            await self._versions.get_by_id(lecture.current_version_id)
            if lecture.current_version_id
            else await self._versions.get_latest_for_lecture(lecture.id)
        )
        scores = version.scores_jsonb if version is not None else None
        total = scores.get("total") if isinstance(scores, dict) else None
        return total if isinstance(total, int) else None
