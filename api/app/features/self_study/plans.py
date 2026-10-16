"""Conversational study plan create/refine + calendar — T-215 / T-216 / T-217."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Literal, cast

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, PermissionDeniedError, ValidationError
from app.core.tenant import get_tenant_type
from app.db.base import not_deleted
from app.features.independent_users.models import IndependentUser, IndependentUserRole
from app.features.independent_users.repository import IndependentUserRepository
from app.features.self_study.categorisation import SelfStudyCategorisationService
from app.features.self_study.events import publish_self_study_plan_generated
from app.features.self_study.granularity import select_granularity
from app.features.self_study.models import (
    IndependentPrepBookTopic,
    IndependentStudentMaterial,
    IndependentStudyPlan,
    IndependentStudyPlanItem,
    MaterialBookType,
    SchoolPrepBookTopic,
    SchoolStudentMaterial,
    SchoolStudyPlan,
    SchoolStudyPlanItem,
    StudyPlanGranularity,
    StudyPlanStatus,
)
from app.features.self_study.schemas import (
    StudyPlanConversationAnswer,
    StudyPlanConversationRead,
    StudyPlanItemRead,
    StudyPlanRead,
    StudyPlanRefineRequest,
)
from app.features.users.models import User, UserRole
from app.features.users.repository import UserRepository
from app.infrastructure.llm.prompts.study_plan_create_v1 import (
    StudyPlanCreateInput,
    WeightedTopic,
)
from app.infrastructure.llm.prompts.study_plan_create_v1 import (
    render as render_create,
)
from app.infrastructure.llm.prompts.study_plan_refine_v1 import (
    StudyPlanRefineInput,
)
from app.infrastructure.llm.prompts.study_plan_refine_v1 import (
    render as render_refine,
)

logger = structlog.get_logger(__name__)

PLAN_GEN_COST_CEILING_USD = 0.50
PLAN_REFINE_COST_CEILING_USD = 0.10

_CONVO_QUESTIONS = (
    "What exam are you preparing for?",
    "When is it?",
    "Which books do you have?",
    "How many hours can you study daily?",
    "Which topics are you already strong in?",
)

# In-process conversation drafts keyed by student_user_id (ephemeral; fine for launch).
_DRAFTS: dict[str, dict[str, Any]] = {}


class SelfStudyPlanService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._school_users = UserRepository(session)
        self._ind_users = IndependentUserRepository(session)
        self._gate = SelfStudyCategorisationService(session)

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

    async def _student_id(
        self, claims: dict[str, object]
    ) -> tuple[str, Literal["school", "independent"]]:
        tenant = get_tenant_type(claims)
        if tenant == "independent":
            return (await self._require_independent_student(claims)).id, "independent"
        return (await self._require_school_student(claims)).id, "school"

    async def conversation_state(self, claims: dict[str, object]) -> StudyPlanConversationRead:
        await self._gate.require_prep_book_or_raise(claims)
        student_id, _ = await self._student_id(claims)
        draft = _DRAFTS.setdefault(
            student_id,
            {"answers": {}, "step": 0, "preserved": True},
        )
        step = int(draft["step"])
        done = step >= len(_CONVO_QUESTIONS)
        return StudyPlanConversationRead(
            step=step,
            total_steps=len(_CONVO_QUESTIONS),
            question=None if done else _CONVO_QUESTIONS[step],
            answers=dict(draft["answers"]),
            complete=done,
            gate_passed=True,
        )

    async def answer_conversation(
        self, claims: dict[str, object], payload: StudyPlanConversationAnswer
    ) -> StudyPlanConversationRead:
        await self._gate.require_prep_book_or_raise(claims)
        student_id, _ = await self._student_id(claims)
        draft = _DRAFTS.setdefault(
            student_id,
            {"answers": {}, "step": 0, "preserved": True},
        )
        step = int(draft["step"])
        if step >= len(_CONVO_QUESTIONS):
            return await self.conversation_state(claims)
        keys = ("exam_name", "exam_date", "books", "daily_hours", "strong_topics")
        draft["answers"][keys[step]] = payload.answer.strip()
        draft["step"] = step + 1
        return await self.conversation_state(claims)

    def _build_items(
        self,
        *,
        exam_date: date,
        granularity: StudyPlanGranularity,
        topics: list[tuple[str, float]],
        daily_hours: int,
        strong: set[str],
    ) -> list[dict[str, Any]]:
        today = date.today()
        if granularity == StudyPlanGranularity.DAY:
            step = 1
        elif granularity == StudyPlanGranularity.THREE_DAY:
            step = 3
        else:
            step = 7
        items: list[dict[str, Any]] = []
        cursor = today
        idx = 0
        while cursor < exam_date and idx < 60:
            end = min(exam_date, cursor + timedelta(days=step - 1))
            topic, weight = topics[idx % len(topics)]
            light = topic.lower() in {s.lower() for s in strong}
            minutes = max(20, int(daily_hours * 60 * (0.5 if light else min(1.0, 0.4 + weight))))
            items.append(
                {
                    "start_date": cursor.isoformat(),
                    "end_date": end.isoformat(),
                    "granularity": granularity.value,
                    "est_minutes": minutes,
                    "subject_color": "#2563eb",
                    "tasks_jsonb": [
                        {
                            "title": topic,
                            "kind": "practice" if weight >= 0.2 else "review",
                        }
                    ],
                }
            )
            cursor = end + timedelta(days=1)
            idx += 1
        # Current-week daily detail for week granularity
        if granularity == StudyPlanGranularity.WEEK:
            week_end = today + timedelta(days=6)
            for d in range(7):
                day = today + timedelta(days=d)
                if day > week_end or day >= exam_date:
                    break
                topic, _w = topics[d % len(topics)]
                items.append(
                    {
                        "start_date": day.isoformat(),
                        "end_date": day.isoformat(),
                        "granularity": StudyPlanGranularity.DAY.value,
                        "est_minutes": max(20, daily_hours * 30),
                        "subject_color": "#16a34a",
                        "tasks_jsonb": [{"title": topic, "kind": "daily"}],
                    }
                )
        return items

    async def _weighted_topics(
        self, *, student_id: str, tenant: Literal["school", "independent"]
    ) -> list[tuple[str, float]]:
        if tenant == "independent":
            mats = await self._session.execute(
                select(IndependentStudentMaterial.id).where(
                    IndependentStudentMaterial.student_user_id == student_id,
                    IndependentStudentMaterial.book_type == MaterialBookType.PREP_QUESTIONS,
                    not_deleted(IndependentStudentMaterial),
                )
            )
            mat_ids = list(mats.scalars().all())
            if not mat_ids:
                return [("General", 1.0)]
            tops = await self._session.execute(
                select(IndependentPrepBookTopic).where(
                    IndependentPrepBookTopic.student_material_id.in_(mat_ids)
                )
            )
            rows = list(tops.scalars().all())
        else:
            mats = await self._session.execute(
                select(SchoolStudentMaterial.id).where(
                    SchoolStudentMaterial.student_user_id == student_id,
                    SchoolStudentMaterial.book_type == MaterialBookType.PREP_QUESTIONS,
                    not_deleted(SchoolStudentMaterial),
                )
            )
            mat_ids = list(mats.scalars().all())
            if not mat_ids:
                return [("General", 1.0)]
            tops = await self._session.execute(
                select(SchoolPrepBookTopic).where(
                    SchoolPrepBookTopic.student_material_id.in_(mat_ids)
                )
            )
            rows = list(tops.scalars().all())
        if not rows:
            return [("General", 1.0)]
        return sorted(
            [(r.topic_label, float(r.weight)) for r in rows],
            key=lambda x: x[1],
            reverse=True,
        )

    async def generate(self, claims: dict[str, object]) -> StudyPlanRead:
        await self._gate.require_prep_book_or_raise(claims)
        student_id, tenant = await self._student_id(claims)
        draft = _DRAFTS.get(student_id)
        if draft is None or int(draft.get("step", 0)) < len(_CONVO_QUESTIONS):
            raise ValidationError("Answer all 5 conversation questions before generating a plan")
        answers = draft["answers"]
        try:
            exam_date = date.fromisoformat(str(answers.get("exam_date", "")).strip()[:10])
        except ValueError as exc:
            raise ValidationError("exam_date must be YYYY-MM-DD") from exc
        try:
            daily_hours = int(str(answers.get("daily_hours", "2")).split()[0])
        except ValueError:
            daily_hours = 2
        strong_raw = str(answers.get("strong_topics", ""))
        strong = [s.strip() for s in strong_raw.split(",") if s.strip()]
        exam_name = str(answers.get("exam_name", "Exam"))
        granularity = select_granularity(exam_date=exam_date)
        topics = await self._weighted_topics(student_id=student_id, tenant=tenant)
        _ = render_create(
            StudyPlanCreateInput(
                exam_name=exam_name,
                exam_date=exam_date.isoformat(),
                daily_hours=daily_hours,
                strong_topics=strong,
                weighted_topics=[WeightedTopic(topic_label=t, weight=w) for t, w in topics],
                granularity=granularity.value,
            )
        )
        item_dicts = self._build_items(
            exam_date=exam_date,
            granularity=granularity,
            topics=topics,
            daily_hours=daily_hours,
            strong=set(strong),
        )

        if tenant == "independent":
            # Archive prior active plan for this exam (one active per exam).
            existing = await self._session.execute(
                select(IndependentStudyPlan).where(
                    IndependentStudyPlan.student_user_id == student_id,
                    IndependentStudyPlan.status == StudyPlanStatus.ACTIVE,
                    not_deleted(IndependentStudyPlan),
                )
            )
            for plan in existing.scalars().all():
                plan.status = StudyPlanStatus.ARCHIVED
                plan.archived_at = datetime.now(timezone.utc)
            plan = IndependentStudyPlan(
                student_user_id=student_id,
                exam_date=exam_date,
                daily_hours=daily_hours,
                strong_topics=strong,
                status=StudyPlanStatus.ACTIVE,
                granularity_current=granularity,
            )
            self._session.add(plan)
            await self._session.flush()
            for d in item_dicts:
                self._session.add(
                    IndependentStudyPlanItem(
                        study_plan_id=plan.id,
                        granularity=StudyPlanGranularity(d["granularity"]),
                        start_date=date.fromisoformat(d["start_date"]),
                        end_date=date.fromisoformat(d["end_date"]),
                        tasks_jsonb=d["tasks_jsonb"],
                        est_minutes=d["est_minutes"],
                        subject_color=d["subject_color"],
                    )
                )
            await self._session.commit()
            await self._session.refresh(plan)
            await publish_self_study_plan_generated(
                payload={
                    "student_user_id": student_id,
                    "plan_id": plan.id,
                    "tenant_type": "independent",
                    "mode": "self_study",
                    "school_id": "",
                    "cost_ceiling_usd": PLAN_GEN_COST_CEILING_USD,
                }
            )
            return await self._read_plan(plan.id, tenant="independent", student_id=student_id)

        school_user = await self._require_school_student(claims)
        existing = await self._session.execute(
            select(SchoolStudyPlan).where(
                SchoolStudyPlan.student_user_id == school_user.id,
                SchoolStudyPlan.status == StudyPlanStatus.ACTIVE,
                not_deleted(SchoolStudyPlan),
            )
        )
        for prior in existing.scalars().all():
            prior.status = StudyPlanStatus.ARCHIVED
            prior.archived_at = datetime.now(timezone.utc)
        school_plan = SchoolStudyPlan(
            student_user_id=school_user.id,
            exam_date=exam_date,
            daily_hours=daily_hours,
            strong_topics=strong,
            status=StudyPlanStatus.ACTIVE,
            granularity_current=granularity,
        )
        self._session.add(school_plan)
        await self._session.flush()
        for d in item_dicts:
            self._session.add(
                SchoolStudyPlanItem(
                    study_plan_id=school_plan.id,
                    granularity=StudyPlanGranularity(d["granularity"]),
                    start_date=date.fromisoformat(d["start_date"]),
                    end_date=date.fromisoformat(d["end_date"]),
                    tasks_jsonb=d["tasks_jsonb"],
                    est_minutes=d["est_minutes"],
                    subject_color=d["subject_color"],
                )
            )
        await self._session.commit()
        await self._session.refresh(school_plan)
        await publish_self_study_plan_generated(
            payload={
                "student_user_id": school_user.id,
                "plan_id": school_plan.id,
                "tenant_type": "school",
                "mode": "self_study",
                "school_id": school_user.school_id or "",
                "cost_ceiling_usd": PLAN_GEN_COST_CEILING_USD,
            }
        )
        return await self._read_plan(school_plan.id, tenant="school", student_id=school_user.id)

    async def refine(
        self, claims: dict[str, object], plan_id: str, payload: StudyPlanRefineRequest
    ) -> StudyPlanRead:
        student_id, tenant = await self._student_id(claims)
        _ = render_refine(
            StudyPlanRefineInput(
                refinement_request=payload.refinement_request,
                affected_items_json="[]",
            )
        )
        # Lightweight refine: halve est_minutes on items mentioning Monday if asked.
        req = payload.refinement_request.lower()
        if tenant == "independent":
            result = await self._session.execute(
                select(IndependentStudyPlan).where(
                    IndependentStudyPlan.id == plan_id,
                    IndependentStudyPlan.student_user_id == student_id,
                    not_deleted(IndependentStudyPlan),
                )
            )
            plan = result.scalar_one_or_none()
            if plan is None:
                raise NotFoundError("Study plan not found")
            items = await self._session.execute(
                select(IndependentStudyPlanItem).where(
                    IndependentStudyPlanItem.study_plan_id == plan_id
                )
            )
            for item in items.scalars().all():
                if "monday" in req and item.start_date.weekday() == 0:
                    item.est_minutes = max(10, item.est_minutes // 2)
                elif "lighter" in req:
                    item.est_minutes = max(10, int(item.est_minutes * 0.75))
            await self._session.commit()
            logger.info(
                "self_study_plan_refined",
                plan_id=plan_id,
                cost_ceiling_usd=PLAN_REFINE_COST_CEILING_USD,
            )
            return await self._read_plan(plan_id, tenant="independent", student_id=student_id)

        result = await self._session.execute(
            select(SchoolStudyPlan).where(
                SchoolStudyPlan.id == plan_id,
                SchoolStudyPlan.student_user_id == student_id,
                not_deleted(SchoolStudyPlan),
            )
        )
        plan = result.scalar_one_or_none()
        if plan is None:
            raise NotFoundError("Study plan not found")
        items = await self._session.execute(
            select(SchoolStudyPlanItem).where(SchoolStudyPlanItem.study_plan_id == plan_id)
        )
        for item in items.scalars().all():
            if "monday" in req and item.start_date.weekday() == 0:
                item.est_minutes = max(10, item.est_minutes // 2)
            elif "lighter" in req:
                item.est_minutes = max(10, int(item.est_minutes * 0.75))
        await self._session.commit()
        return await self._read_plan(plan_id, tenant="school", student_id=student_id)

    async def get_active(self, claims: dict[str, object]) -> StudyPlanRead | None:
        student_id, tenant = await self._student_id(claims)
        if tenant == "independent":
            result = await self._session.execute(
                select(IndependentStudyPlan).where(
                    IndependentStudyPlan.student_user_id == student_id,
                    IndependentStudyPlan.status == StudyPlanStatus.ACTIVE,
                    not_deleted(IndependentStudyPlan),
                )
            )
            plan = result.scalar_one_or_none()
            if plan is None:
                return None
            return await self._read_plan(plan.id, tenant="independent", student_id=student_id)
        result = await self._session.execute(
            select(SchoolStudyPlan).where(
                SchoolStudyPlan.student_user_id == student_id,
                SchoolStudyPlan.status == StudyPlanStatus.ACTIVE,
                not_deleted(SchoolStudyPlan),
            )
        )
        plan = result.scalar_one_or_none()
        if plan is None:
            return None
        return await self._read_plan(plan.id, tenant="school", student_id=student_id)

    async def _read_plan(
        self,
        plan_id: str,
        *,
        tenant: Literal["school", "independent"],
        student_id: str,
    ) -> StudyPlanRead:
        if tenant == "independent":
            result = await self._session.execute(
                select(IndependentStudyPlan).where(
                    IndependentStudyPlan.id == plan_id,
                    IndependentStudyPlan.student_user_id == student_id,
                )
            )
            plan = result.scalar_one_or_none()
            if plan is None:
                raise NotFoundError("Study plan not found")
            items_r = await self._session.execute(
                select(IndependentStudyPlanItem).where(
                    IndependentStudyPlanItem.study_plan_id == plan_id
                )
            )
            items = list(items_r.scalars().all())
        else:
            result = await self._session.execute(
                select(SchoolStudyPlan).where(
                    SchoolStudyPlan.id == plan_id,
                    SchoolStudyPlan.student_user_id == student_id,
                )
            )
            plan = result.scalar_one_or_none()
            if plan is None:
                raise NotFoundError("Study plan not found")
            items_r = await self._session.execute(
                select(SchoolStudyPlanItem).where(SchoolStudyPlanItem.study_plan_id == plan_id)
            )
            items = list(items_r.scalars().all())
        return StudyPlanRead(
            id=plan.id,
            tenant_type=tenant,
            status=cast(Literal["active", "archived"], plan.status.value),
            exam_date=plan.exam_date.isoformat() if plan.exam_date else None,
            daily_hours=plan.daily_hours,
            strong_topics=list(plan.strong_topics or []),
            granularity_current=cast(
                Literal["day", "3day", "week"], plan.granularity_current.value
            ),
            items=[
                StudyPlanItemRead(
                    id=i.id,
                    granularity=cast(Literal["day", "3day", "week"], i.granularity.value),
                    start_date=i.start_date.isoformat(),
                    end_date=i.end_date.isoformat(),
                    est_minutes=i.est_minutes,
                    subject_color=i.subject_color,
                    tasks=list(i.tasks_jsonb or []),
                )
                for i in items
            ],
        )

    async def export_ics(self, claims: dict[str, object], plan_id: str) -> str:
        student_id, tenant = await self._student_id(claims)
        plan = await self._read_plan(plan_id, tenant=tenant, student_id=student_id)
        lines = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//IqbalAI//SelfStudy//EN",
        ]
        for item in plan.items:
            title = "Study"
            if item.tasks and isinstance(item.tasks[0], dict):
                title = str(item.tasks[0].get("title") or "Study")
            uid = f"{item.id}@iqbalai"
            lines.extend(
                [
                    "BEGIN:VEVENT",
                    f"UID:{uid}",
                    f"DTSTART;VALUE=DATE:{item.start_date.replace('-', '')}",
                    f"DTEND;VALUE=DATE:{item.end_date.replace('-', '')}",
                    f"SUMMARY:{title}",
                    f"DESCRIPTION:Est {item.est_minutes} minutes",
                    "END:VEVENT",
                ]
            )
        lines.append("END:VCALENDAR")
        return "\r\n".join(lines) + "\r\n"
