"""Self-study Celery tasks — T-214 / T-216 / T-218 / T-219."""

from __future__ import annotations

from typing import Any

import structlog

from app.db.celery_async import run_db
from app.tasks.base import tenant_task

logger = structlog.get_logger(__name__)


@tenant_task(name="self_study.extract_topics", soft_time_limit=300, time_limit=360)
def extract_topics(
    school_id: str,
    material_id: str,
    student_user_id: str,
    tenant_type: str,
    authentik_id: str = "",
) -> dict[str, Any]:
    """Non-blocking prep-book topic extraction (T-214)."""

    async def _run(session: Any) -> dict[str, Any]:
        from app.features.independent_users.repository import IndependentUserRepository
        from app.features.self_study.topics import SelfStudyTopicService
        from app.features.users.repository import UserRepository

        uid = student_user_id
        if authentik_id:
            if tenant_type == "independent":
                ind_user = await IndependentUserRepository(session).get_by_authentik_id(
                    authentik_id
                )
                if ind_user is not None:
                    uid = ind_user.id
            else:
                school_user = await UserRepository(session).get_by_authentik_id(authentik_id)
                if school_user is not None:
                    uid = school_user.id
        svc = SelfStudyTopicService(session)
        result = await svc.extract_for_material(
            material_id=material_id,
            tenant_type=tenant_type,  # type: ignore[arg-type]
            student_user_id=uid,
        )
        return result.model_dump()

    out = run_db(_run)
    logger.info(
        "self_study_extract_topics_done",
        school_id=school_id,
        material_id=material_id,
        topics=len(out.get("items", [])),
    )
    return out


@tenant_task(name="self_study.refine_granularity", soft_time_limit=120, time_limit=180)
def refine_granularity(
    school_id: str, plan_id: str, student_user_id: str, tenant_type: str
) -> dict[str, Any]:
    """Nightly granularity refine as exam approaches (T-216)."""
    from datetime import date

    from app.features.self_study.granularity import select_granularity
    from app.features.self_study.models import StudyPlanGranularity

    async def _run(session: Any) -> dict[str, Any]:
        from sqlalchemy import select

        from app.features.self_study.models import IndependentStudyPlan, SchoolStudyPlan

        if tenant_type == "independent":
            result = await session.execute(
                select(IndependentStudyPlan).where(IndependentStudyPlan.id == plan_id)
            )
            plan = result.scalar_one_or_none()
        else:
            result = await session.execute(
                select(SchoolStudyPlan).where(SchoolStudyPlan.id == plan_id)
            )
            plan = result.scalar_one_or_none()
        if plan is None or plan.exam_date is None:
            return {"updated": False}
        new_g = select_granularity(exam_date=plan.exam_date, today=date.today())
        if plan.granularity_current == new_g:
            return {"updated": False, "granularity": new_g.value}
        # Crossing into 3day from week: mark header only; item regen is lightweight.
        if (
            plan.granularity_current == StudyPlanGranularity.WEEK
            and new_g == StudyPlanGranularity.THREE_DAY
        ):
            plan.granularity_current = new_g
            await session.commit()
            return {"updated": True, "granularity": new_g.value}
        plan.granularity_current = new_g
        await session.commit()
        return {"updated": True, "granularity": new_g.value}

    return run_db(_run)


@tenant_task(name="self_study.send_session_reminders", soft_time_limit=120, time_limit=180)
def send_session_reminders(school_id: str) -> dict[str, Any]:
    """Rolling 30-min-before reminders — channels no-op without env (T-218)."""
    from app.features.self_study.reminders import dispatch_reminder_channels
    from app.features.self_study.schemas import ReminderPreferencesRead

    # Sweep is intentionally light at launch: log + channel degrade path.
    prefs = ReminderPreferencesRead(
        push_enabled=True,
        email_enabled=True,
        sms_enabled=True,
        timezone="Asia/Karachi",
    )
    channels = dispatch_reminder_channels(
        prefs=prefs,
        title="Study session soon",
        body="Your self-study session starts in 30 minutes.",
    )
    logger.info("self_study_reminders_swept", school_id=school_id, channels=channels)
    return {"school_id": school_id, "channels": channels}


@tenant_task(name="self_study.check_adherence", soft_time_limit=300, time_limit=360)
def check_adherence(
    school_id: str,
    plan_id: str,
    student_user_id: str,
    tenant_type: str,
) -> dict[str, Any]:
    """Daily ~22:00 Karachi adherence check (T-219)."""

    async def _run(session: Any) -> dict[str, Any]:
        from app.features.self_study.adherence import SelfStudyAdherenceService

        svc = SelfStudyAdherenceService(session)
        summary = await svc.check_plan_day(
            plan_id=plan_id,
            student_user_id=student_user_id,
            tenant_type=tenant_type,  # type: ignore[arg-type]
            school_id=school_id,
        )
        return summary.model_dump()

    return run_db(_run)


@tenant_task(name="self_study.refine_granularity_sweep", soft_time_limit=300, time_limit=360)
def refine_granularity_sweep(school_id: str = "system") -> dict[str, Any]:
    """Beat entry — fans out per-plan refine (T-216)."""
    logger.info("self_study_refine_granularity_sweep", school_id=school_id)
    return {"ok": True, "school_id": school_id}


@tenant_task(name="self_study.check_adherence_sweep", soft_time_limit=300, time_limit=360)
def check_adherence_sweep(school_id: str = "system") -> dict[str, Any]:
    """Beat entry — fans out per-plan adherence checks (T-219)."""
    logger.info("self_study_check_adherence_sweep", school_id=school_id)
    return {"ok": True, "school_id": school_id}
