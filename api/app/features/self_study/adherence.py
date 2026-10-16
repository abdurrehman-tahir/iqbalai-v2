"""Plan adherence check — T-219 (Flow 8 §3.10). Does NOT compute pass probability."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Literal, cast

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, PermissionDeniedError
from app.core.tenant import get_tenant_type
from app.db.base import not_deleted
from app.features.independent_users.models import IndependentUser, IndependentUserRole
from app.features.independent_users.repository import IndependentUserRepository
from app.features.self_study.events import (
    publish_self_study_adherence_alert,
    publish_self_study_adherence_updated,
)
from app.features.self_study.models import (
    IndependentStudyPlan,
    IndependentStudyPlanDay,
    IndependentStudyPlanItem,
    SchoolStudyPlan,
    SchoolStudyPlanDay,
    SchoolStudyPlanItem,
    StudyPlanStatus,
)
from app.features.self_study.schemas import AdherenceDayRead, AdherenceSummaryRead
from app.features.self_study.sessions import (
    IndependentSelfStudySession,
    SchoolSelfStudySession,
    SelfStudySessionStatus,
)
from app.features.users.models import User, UserRole
from app.features.users.repository import UserRepository

logger = structlog.get_logger(__name__)


def _task_title(tasks_jsonb: list[object] | None) -> str:
    raw = tasks_jsonb or [{}]
    first = cast(dict[str, Any], raw[0] if raw else {})
    return str(first.get("title", "task"))


class SelfStudyAdherenceService:
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

    async def check_plan_day(
        self,
        *,
        plan_id: str,
        student_user_id: str,
        tenant_type: Literal["school", "independent"],
        school_id: str,
        day: date | None = None,
    ) -> AdherenceSummaryRead:
        """Infer completion from session activity on the day — not a checkbox."""
        target = day or date.today()
        if tenant_type == "independent":
            return await self._check_independent(
                plan_id=plan_id,
                student_user_id=student_user_id,
                target=target,
            )
        return await self._check_school(
            plan_id=plan_id,
            student_user_id=student_user_id,
            school_id=school_id,
            target=target,
        )

    async def _check_independent(
        self,
        *,
        plan_id: str,
        student_user_id: str,
        target: date,
    ) -> AdherenceSummaryRead:
        alert_fired = False
        plan_r = await self._session.execute(
            select(IndependentStudyPlan).where(
                IndependentStudyPlan.id == plan_id,
                IndependentStudyPlan.student_user_id == student_user_id,
                IndependentStudyPlan.status == StudyPlanStatus.ACTIVE,
                not_deleted(IndependentStudyPlan),
            )
        )
        plan = plan_r.scalar_one_or_none()
        if plan is None:
            raise NotFoundError("Active study plan not found")
        items_r = await self._session.execute(
            select(IndependentStudyPlanItem).where(
                IndependentStudyPlanItem.study_plan_id == plan_id,
                IndependentStudyPlanItem.start_date <= target,
                IndependentStudyPlanItem.end_date >= target,
            )
        )
        scheduled = list(items_r.scalars().all())
        sessions_r = await self._session.execute(
            select(IndependentSelfStudySession).where(
                IndependentSelfStudySession.student_user_id == student_user_id,
            )
        )
        sessions = list(sessions_r.scalars().all())
        activity = any(
            s.started_at.date() == target
            and s.status in (SelfStudySessionStatus.ACTIVE, SelfStudySessionStatus.ENDED)
            for s in sessions
        )
        scheduled_tasks: list[object] = [
            {"id": i.id, "title": _task_title(i.tasks_jsonb)} for i in scheduled
        ]
        completed: list[object] = scheduled_tasks if activity and scheduled_tasks else []
        pct = (
            (len(completed) / len(scheduled_tasks))
            if scheduled_tasks
            else (1.0 if activity else 0.0)
        )

        day_r = await self._session.execute(
            select(IndependentStudyPlanDay).where(
                IndependentStudyPlanDay.study_plan_id == plan_id,
                IndependentStudyPlanDay.day_date == target,
            )
        )
        day_row = day_r.scalar_one_or_none()
        prev_miss = 0
        if day_row is None:
            yday = target.fromordinal(target.toordinal() - 1)
            y_r = await self._session.execute(
                select(IndependentStudyPlanDay).where(
                    IndependentStudyPlanDay.study_plan_id == plan_id,
                    IndependentStudyPlanDay.day_date == yday,
                )
            )
            y = y_r.scalar_one_or_none()
            prev_miss = y.consecutive_miss_count if y and y.adherence_pct <= 0 else 0
            day_row = IndependentStudyPlanDay(
                study_plan_id=plan_id,
                day_date=target,
                scheduled_tasks_jsonb=scheduled_tasks,
                completed_tasks_jsonb=completed,
                adherence_pct=pct,
                consecutive_miss_count=0,
            )
            self._session.add(day_row)
        else:
            prev_miss = day_row.consecutive_miss_count
            day_row.scheduled_tasks_jsonb = scheduled_tasks
            day_row.completed_tasks_jsonb = completed
            day_row.adherence_pct = pct

        if pct <= 0 and scheduled_tasks:
            day_row.consecutive_miss_count = prev_miss + 1
        else:
            day_row.consecutive_miss_count = 0

        if day_row.consecutive_miss_count >= 2 and day_row.alerted_at is None:
            day_row.alerted_at = datetime.now(timezone.utc)
            alert_fired = True
            await publish_self_study_adherence_alert(
                payload={
                    "student_user_id": student_user_id,
                    "plan_id": plan_id,
                    "tenant_type": "independent",
                    "mode": "self_study",
                    "school_id": "",
                    "consecutive_miss_count": day_row.consecutive_miss_count,
                }
            )

        await self._session.commit()
        await self._session.refresh(day_row)
        await publish_self_study_adherence_updated(
            payload={
                "student_user_id": student_user_id,
                "plan_id": plan_id,
                "tenant_type": "independent",
                "mode": "self_study",
                "school_id": "",
                "adherence_pct": day_row.adherence_pct,
                "day_date": target.isoformat(),
            }
        )
        return AdherenceSummaryRead(
            plan_id=plan_id,
            days=[
                AdherenceDayRead(
                    day_date=day_row.day_date.isoformat(),
                    adherence_pct=day_row.adherence_pct,
                    consecutive_miss_count=day_row.consecutive_miss_count,
                    alerted=day_row.alerted_at is not None,
                )
            ],
            alert_fired=alert_fired,
        )

    async def _check_school(
        self,
        *,
        plan_id: str,
        student_user_id: str,
        school_id: str,
        target: date,
    ) -> AdherenceSummaryRead:
        alert_fired = False
        plan_r = await self._session.execute(
            select(SchoolStudyPlan).where(
                SchoolStudyPlan.id == plan_id,
                SchoolStudyPlan.student_user_id == student_user_id,
                SchoolStudyPlan.status == StudyPlanStatus.ACTIVE,
                not_deleted(SchoolStudyPlan),
            )
        )
        plan = plan_r.scalar_one_or_none()
        if plan is None:
            raise NotFoundError("Active study plan not found")
        items_r = await self._session.execute(
            select(SchoolStudyPlanItem).where(
                SchoolStudyPlanItem.study_plan_id == plan_id,
                SchoolStudyPlanItem.start_date <= target,
                SchoolStudyPlanItem.end_date >= target,
            )
        )
        scheduled = list(items_r.scalars().all())
        sessions_r = await self._session.execute(
            select(SchoolSelfStudySession).where(
                SchoolSelfStudySession.student_user_id == student_user_id,
            )
        )
        sessions = list(sessions_r.scalars().all())
        activity = any(
            s.started_at.date() == target
            and s.status in (SelfStudySessionStatus.ACTIVE, SelfStudySessionStatus.ENDED)
            for s in sessions
        )
        scheduled_tasks: list[object] = [
            {"id": i.id, "title": _task_title(i.tasks_jsonb)} for i in scheduled
        ]
        completed: list[object] = scheduled_tasks if activity and scheduled_tasks else []
        pct = (
            (len(completed) / len(scheduled_tasks))
            if scheduled_tasks
            else (1.0 if activity else 0.0)
        )

        day_r = await self._session.execute(
            select(SchoolStudyPlanDay).where(
                SchoolStudyPlanDay.study_plan_id == plan_id,
                SchoolStudyPlanDay.day_date == target,
            )
        )
        day_row = day_r.scalar_one_or_none()
        prev_miss = 0
        if day_row is None:
            yday = target.fromordinal(target.toordinal() - 1)
            y_r = await self._session.execute(
                select(SchoolStudyPlanDay).where(
                    SchoolStudyPlanDay.study_plan_id == plan_id,
                    SchoolStudyPlanDay.day_date == yday,
                )
            )
            y = y_r.scalar_one_or_none()
            prev_miss = y.consecutive_miss_count if y and y.adherence_pct <= 0 else 0
            day_row = SchoolStudyPlanDay(
                study_plan_id=plan_id,
                day_date=target,
                scheduled_tasks_jsonb=scheduled_tasks,
                completed_tasks_jsonb=completed,
                adherence_pct=pct,
                consecutive_miss_count=0,
            )
            self._session.add(day_row)
        else:
            prev_miss = day_row.consecutive_miss_count
            day_row.scheduled_tasks_jsonb = scheduled_tasks
            day_row.completed_tasks_jsonb = completed
            day_row.adherence_pct = pct

        if pct <= 0 and scheduled_tasks:
            day_row.consecutive_miss_count = prev_miss + 1
        else:
            day_row.consecutive_miss_count = 0

        if day_row.consecutive_miss_count >= 2 and day_row.alerted_at is None:
            day_row.alerted_at = datetime.now(timezone.utc)
            alert_fired = True
            await publish_self_study_adherence_alert(
                payload={
                    "student_user_id": student_user_id,
                    "plan_id": plan_id,
                    "tenant_type": "school",
                    "mode": "self_study",
                    "school_id": school_id,
                    "consecutive_miss_count": day_row.consecutive_miss_count,
                }
            )

        await self._session.commit()
        await self._session.refresh(day_row)
        await publish_self_study_adherence_updated(
            payload={
                "student_user_id": student_user_id,
                "plan_id": plan_id,
                "tenant_type": "school",
                "mode": "self_study",
                "school_id": school_id,
                "adherence_pct": day_row.adherence_pct,
                "day_date": target.isoformat(),
            }
        )
        return AdherenceSummaryRead(
            plan_id=plan_id,
            days=[
                AdherenceDayRead(
                    day_date=day_row.day_date.isoformat(),
                    adherence_pct=day_row.adherence_pct,
                    consecutive_miss_count=day_row.consecutive_miss_count,
                    alerted=day_row.alerted_at is not None,
                )
            ],
            alert_fired=alert_fired,
        )

    async def check_for_claims(
        self, claims: dict[str, object], *, plan_id: str
    ) -> AdherenceSummaryRead:
        tenant = get_tenant_type(claims)
        if tenant == "independent":
            ind_user = await self._require_independent_student(claims)
            return await self.check_plan_day(
                plan_id=plan_id,
                student_user_id=ind_user.id,
                tenant_type="independent",
                school_id="",
            )
        school_user = await self._require_school_student(claims)
        return await self.check_plan_day(
            plan_id=plan_id,
            student_user_id=school_user.id,
            tenant_type="school",
            school_id=school_user.school_id or "",
        )
