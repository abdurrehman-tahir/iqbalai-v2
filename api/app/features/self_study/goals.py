"""Daily goal service — T-211 (Flow 8 §3.2)."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Literal
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, PermissionDeniedError
from app.core.tenant import get_tenant_type
from app.features.independent_users.models import IndependentUser, IndependentUserRole
from app.features.independent_users.repository import IndependentUserRepository
from app.features.self_study.events import (
    publish_self_study_goal_achieved,
    publish_self_study_goal_set,
)
from app.features.self_study.models import IndependentStudentGoal, SchoolStudentGoal
from app.features.self_study.schemas import (
    SelfStudyGoalAchieve,
    SelfStudyGoalRead,
    SelfStudyGoalSet,
)
from app.features.users.models import User, UserRole
from app.features.users.repository import UserRepository

logger = structlog.get_logger(__name__)

_KARACHI = ZoneInfo("Asia/Karachi")
MIN_SESSION_SECONDS_FOR_CHECK = 5 * 60


def today_karachi() -> date:
    return datetime.now(_KARACHI).date()


def _to_read(
    row: SchoolStudentGoal | IndependentStudentGoal,
    *,
    tenant_type: Literal["school", "independent"],
) -> SelfStudyGoalRead:
    return SelfStudyGoalRead(
        id=row.id,
        tenant_type=tenant_type,
        goal_date=row.goal_date.isoformat(),
        goal_text=row.goal_text,
        achieved=row.achieved,
        achievement_check_pending=row.achievement_check_at is None,
    )


class SelfStudyGoalService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._school_users = UserRepository(session)
        self._ind_users = IndependentUserRepository(session)

    async def _require_school_student(self, claims: dict[str, object]) -> User:
        if str(claims.get("role", "")) != UserRole.STUDENT.value:
            raise PermissionDeniedError("Requires a school student account")
        user = await self._school_users.get_by_authentik_id(str(claims.get("sub", "")))
        if user is None or user.role != UserRole.STUDENT:
            raise NotFoundError("Student not found")
        return user

    async def _require_independent_student(self, claims: dict[str, object]) -> IndependentUser:
        user = await self._ind_users.get_by_authentik_id(str(claims.get("sub", "")))
        if user is None or user.role != IndependentUserRole.INDEPENDENT_STUDENT:
            raise NotFoundError("Independent student not found")
        return user

    async def get_today(self, claims: dict[str, object]) -> SelfStudyGoalRead | None:
        tenant = get_tenant_type(claims)
        day = today_karachi()
        if tenant == "independent":
            ind_user = await self._require_independent_student(claims)
            ind_result = await self._session.execute(
                select(IndependentStudentGoal).where(
                    IndependentStudentGoal.student_user_id == ind_user.id,
                    IndependentStudentGoal.goal_date == day,
                )
            )
            ind_row = ind_result.scalar_one_or_none()
            return _to_read(ind_row, tenant_type="independent") if ind_row else None

        school_user = await self._require_school_student(claims)
        school_result = await self._session.execute(
            select(SchoolStudentGoal).where(
                SchoolStudentGoal.student_user_id == school_user.id,
                SchoolStudentGoal.goal_date == day,
            )
        )
        school_row = school_result.scalar_one_or_none()
        return _to_read(school_row, tenant_type="school") if school_row else None

    async def set_goal(
        self,
        payload: SelfStudyGoalSet,
        claims: dict[str, object],
    ) -> SelfStudyGoalRead:
        tenant = get_tenant_type(claims)
        day = today_karachi()
        text = payload.goal_text.strip()
        if tenant == "independent":
            ind_user = await self._require_independent_student(claims)
            ind_result = await self._session.execute(
                select(IndependentStudentGoal).where(
                    IndependentStudentGoal.student_user_id == ind_user.id,
                    IndependentStudentGoal.goal_date == day,
                )
            )
            existing_ind = ind_result.scalar_one_or_none()
            if existing_ind is not None and not payload.confirm_replace:
                if existing_ind.goal_text != text:
                    raise ConflictError(
                        "A goal already exists for today — confirm replace to overwrite"
                    )
                return _to_read(existing_ind, tenant_type="independent")
            if existing_ind is None:
                ind_row = IndependentStudentGoal(
                    student_user_id=ind_user.id,
                    goal_date=day,
                    goal_text=text,
                )
                self._session.add(ind_row)
            else:
                ind_row = existing_ind
                ind_row.goal_text = text
                ind_row.achieved = None
                ind_row.achieved_response_at = None
                ind_row.achievement_check_at = None
            await self._session.commit()
            await self._session.refresh(ind_row)
            await publish_self_study_goal_set(
                payload={
                    "student_user_id": ind_user.id,
                    "goal_id": ind_row.id,
                    "goal_text": ind_row.goal_text,
                    "goal_date": ind_row.goal_date.isoformat(),
                    "tenant_type": "independent",
                    "mode": "self_study",
                    "school_id": "",
                }
            )
            logger.info("self_study_goal_set", tenant="independent", goal_id=ind_row.id)
            return _to_read(ind_row, tenant_type="independent")

        school_user = await self._require_school_student(claims)
        school_result = await self._session.execute(
            select(SchoolStudentGoal).where(
                SchoolStudentGoal.student_user_id == school_user.id,
                SchoolStudentGoal.goal_date == day,
            )
        )
        existing_school = school_result.scalar_one_or_none()
        if existing_school is not None and not payload.confirm_replace:
            if existing_school.goal_text != text:
                raise ConflictError(
                    "A goal already exists for today — confirm replace to overwrite"
                )
            return _to_read(existing_school, tenant_type="school")
        if existing_school is None:
            school_row = SchoolStudentGoal(
                student_user_id=school_user.id,
                goal_date=day,
                goal_text=text,
            )
            self._session.add(school_row)
        else:
            school_row = existing_school
            school_row.goal_text = text
            school_row.achieved = None
            school_row.achieved_response_at = None
            school_row.achievement_check_at = None
        await self._session.commit()
        await self._session.refresh(school_row)
        await publish_self_study_goal_set(
            payload={
                "student_user_id": school_user.id,
                "goal_id": school_row.id,
                "goal_text": school_row.goal_text,
                "goal_date": school_row.goal_date.isoformat(),
                "tenant_type": "school",
                "mode": "self_study",
                "school_id": school_user.school_id or "",
            }
        )
        logger.info("self_study_goal_set", tenant="school", goal_id=school_row.id)
        return _to_read(school_row, tenant_type="school")

    async def respond_achievement(
        self,
        payload: SelfStudyGoalAchieve,
        claims: dict[str, object],
        *,
        session_duration_seconds: int,
    ) -> SelfStudyGoalRead:
        """End-of-session check — fires once/day for sessions >5 min; skippable."""
        # Short sessions: skip silently (check only fires after >5 min).
        if session_duration_seconds < MIN_SESSION_SECONDS_FOR_CHECK:
            today = await self.get_today(claims)
            if today is None:
                raise NotFoundError("No goal set for today")
            return today
        tenant = get_tenant_type(claims)
        day = today_karachi()
        now = datetime.now(timezone.utc)

        if tenant == "independent":
            ind_user = await self._require_independent_student(claims)
            ind_result = await self._session.execute(
                select(IndependentStudentGoal).where(
                    IndependentStudentGoal.student_user_id == ind_user.id,
                    IndependentStudentGoal.goal_date == day,
                )
            )
            ind_row = ind_result.scalar_one_or_none()
            if ind_row is None:
                raise NotFoundError("No goal set for today")
            if ind_row.achievement_check_at is not None:
                return _to_read(ind_row, tenant_type="independent")
            ind_row.achievement_check_at = now
            if not payload.skip:
                ind_row.achieved = payload.achieved
                ind_row.achieved_response_at = now
            await self._session.commit()
            await self._session.refresh(ind_row)
            if not payload.skip:
                await publish_self_study_goal_achieved(
                    payload={
                        "student_user_id": ind_user.id,
                        "goal_id": ind_row.id,
                        "achieved": ind_row.achieved,
                        "tenant_type": "independent",
                        "mode": "self_study",
                        "school_id": "",
                    }
                )
            return _to_read(ind_row, tenant_type="independent")

        school_user = await self._require_school_student(claims)
        school_result = await self._session.execute(
            select(SchoolStudentGoal).where(
                SchoolStudentGoal.student_user_id == school_user.id,
                SchoolStudentGoal.goal_date == day,
            )
        )
        school_row = school_result.scalar_one_or_none()
        if school_row is None:
            raise NotFoundError("No goal set for today")
        if school_row.achievement_check_at is not None:
            return _to_read(school_row, tenant_type="school")
        school_row.achievement_check_at = now
        if not payload.skip:
            school_row.achieved = payload.achieved
            school_row.achieved_response_at = now
        await self._session.commit()
        await self._session.refresh(school_row)
        if not payload.skip:
            await publish_self_study_goal_achieved(
                payload={
                    "student_user_id": school_user.id,
                    "goal_id": school_row.id,
                    "achieved": school_row.achieved,
                    "tenant_type": "school",
                    "mode": "self_study",
                    "school_id": school_user.school_id or "",
                }
            )
        return _to_read(school_row, tenant_type="school")


def session_duration_seconds(started_at: datetime) -> int:
    now = datetime.now(timezone.utc)
    start = started_at if started_at.tzinfo else started_at.replace(tzinfo=timezone.utc)
    return max(0, int((now - start).total_seconds()))
