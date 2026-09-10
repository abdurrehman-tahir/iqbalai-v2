"""M-07 Exam Framework milestone E2E smoke test — T-099.

Drives the full framework lifecycle through the real service layer against a shared
in-memory store (no live DB, no live network — SearXNG/web_fetch are replaced by a mocked
research outcome, so this runs in CI): create DRAFT -> research -> PENDING_APPROVAL ->
approve -> PUBLISHED v1 -> student selects (region + grade filter asserted) -> plan renders
-> quarterly refresh -> v2 approved -> the v1-pinned student sees the opt-in switch banner
-> switch. Also asserts the M-07 audit actions are registered.

Notifications + NATS events are post-commit best-effort side effects and are stubbed here;
they are covered by test_notifications.py.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from app.features.exam_frameworks import research as research_mod
from app.features.exam_frameworks import service as service_mod
from app.features.exam_frameworks import student_service as student_mod
from app.features.exam_frameworks.models import (
    ExamFramework,
    FrameworkResearchJob,
    FrameworkStatus,
    FrameworkStudyPlan,
    SelectionStatus,
    SelectionTenantType,
    StudentFrameworkSelection,
    StudyPlanStatus,
)
from app.features.exam_frameworks.research import ResearchOutcome
from app.features.exam_frameworks.schemas import (
    ExamFrameworkCreate,
    ExamStrategy,
    FrameworkTopic,
    SourceCitation,
    WeeklyPacing,
)
from app.features.exam_frameworks.service import ExamFrameworkService
from app.features.exam_frameworks.student_service import StudentFrameworkService

REGION_ANY = "any"


class _Store:
    frameworks: dict[str, ExamFramework] = {}
    plans: dict[str, FrameworkStudyPlan] = {}
    jobs: dict[str, FrameworkResearchJob] = {}
    selections: dict[str, StudentFrameworkSelection] = {}


class _FakeRepo:
    """One in-memory repo standing in for BOTH the admin + student repositories."""

    def __init__(self, session: Any) -> None:
        pass

    # --- frameworks ---
    async def get_by_id(self, id: str) -> ExamFramework | None:
        return _Store.frameworks.get(id)

    async def get_framework(self, framework_id: str) -> ExamFramework | None:
        fw = _Store.frameworks.get(framework_id)
        return fw if fw is not None and fw.deleted_at is None else None

    async def get_published_framework(self, framework_id: str) -> ExamFramework | None:
        fw = _Store.frameworks.get(framework_id)
        if fw is None or fw.status != FrameworkStatus.PUBLISHED or fw.deleted_at is not None:
            return None
        return fw

    async def create(self, framework: ExamFramework) -> ExamFramework:
        _Store.frameworks[framework.id] = framework
        return framework

    async def refresh_framework(self, framework: ExamFramework) -> None:
        pass

    async def list_available_frameworks(self, region: str, grade: int) -> list[ExamFramework]:
        return [
            f
            for f in _Store.frameworks.values()
            if f.status == FrameworkStatus.PUBLISHED
            and f.deleted_at is None
            and (f.region == region or f.region == REGION_ANY)
            and grade in f.target_grade_range
        ]

    # --- plans / jobs ---
    def add(self, obj: Any) -> None:
        if isinstance(obj, FrameworkResearchJob):
            _Store.jobs[obj.id] = obj
        elif isinstance(obj, FrameworkStudyPlan):
            _Store.plans[obj.id] = obj
        elif isinstance(obj, StudentFrameworkSelection):
            _Store.selections[obj.id] = obj

    async def get_job_by_id(self, job_id: str) -> FrameworkResearchJob | None:
        return _Store.jobs.get(job_id)

    async def next_plan_version(self, framework_id: str) -> int:
        versions = [p.version for p in _Store.plans.values() if p.framework_id == framework_id]
        return (max(versions) if versions else 0) + 1

    async def get_pending_plan(self, framework_id: str) -> FrameworkStudyPlan | None:
        pend = [
            p
            for p in _Store.plans.values()
            if p.framework_id == framework_id and p.status == StudyPlanStatus.PENDING_APPROVAL
        ]
        return max(pend, key=lambda p: p.version) if pend else None

    async def get_current_published_plan(self, framework_id: str) -> FrameworkStudyPlan | None:
        appr = [
            p
            for p in _Store.plans.values()
            if p.framework_id == framework_id and p.status == StudyPlanStatus.APPROVED
        ]
        return max(appr, key=lambda p: p.version) if appr else None

    async def get_plan_by_version(
        self, framework_id: str, version: int
    ) -> FrameworkStudyPlan | None:
        for p in _Store.plans.values():
            if p.framework_id == framework_id and p.version == version:
                return p
        return None

    # --- selections ---
    async def list_selections(
        self, tenant_type: SelectionTenantType, student_user_id: str
    ) -> list[StudentFrameworkSelection]:
        return [
            s
            for s in _Store.selections.values()
            if s.tenant_type == tenant_type and s.student_user_id == student_user_id
        ]

    async def get_active_selection(
        self, tenant_type: SelectionTenantType, student_user_id: str, framework_id: str
    ) -> StudentFrameworkSelection | None:
        for s in _Store.selections.values():
            if (
                s.tenant_type == tenant_type
                and s.student_user_id == student_user_id
                and s.framework_id == framework_id
                and s.status == SelectionStatus.ACTIVE
            ):
                return s
        return None

    async def get_selection_by_id(self, selection_id: str) -> StudentFrameworkSelection | None:
        return _Store.selections.get(selection_id)

    async def list_active_selections_pinned_below(
        self, framework_id: str, version: int
    ) -> list[StudentFrameworkSelection]:
        return [
            s
            for s in _Store.selections.values()
            if s.framework_id == framework_id
            and s.status == SelectionStatus.ACTIVE
            and s.pinned_version < version
        ]

    # --- shared ---
    async def commit(self) -> None:
        pass

    async def refresh(self, obj: Any) -> None:
        pass


def _outcome() -> ResearchOutcome:
    return ResearchOutcome(
        partial=False,
        topics=[
            FrameworkTopic(
                topic_name="Newton's Laws",
                priority_weight=0.9,
                exam_frequency="every_year",
                recommended_hours=6,
            )
        ],
        weekly_pacing=[WeeklyPacing(week_from_exam=12, hours_estimated=10)],
        exam_strategy=ExamStrategy(scoring_strategy="Attempt MCQs first"),
        sources=[SourceCitation(url="https://board.example/pastpapers", title="Past papers")],
        cost_usd=Decimal("2.50"),
    )


@pytest.fixture(autouse=True)
def _patch(monkeypatch: pytest.MonkeyPatch) -> None:
    _Store.frameworks = {}
    _Store.plans = {}
    _Store.jobs = {}
    _Store.selections = {}

    monkeypatch.setattr(service_mod, "ExamFrameworkRepository", _FakeRepo)
    monkeypatch.setattr(student_mod, "StudentFrameworkRepository", _FakeRepo)

    async def _noop(*args: Any, **kwargs: Any) -> None:
        return None

    monkeypatch.setattr(service_mod, "audit", _noop)

    async def _fake_run_research(framework: ExamFramework, **kwargs: Any) -> ResearchOutcome:
        return _outcome()

    monkeypatch.setattr(research_mod, "run_research", _fake_run_research)

    # trigger_research/trigger_refresh enqueue a Celery task; stub the broker call.
    class _FakeTask:
        @staticmethod
        def delay(framework_id: str, job_id: str) -> None:
            return None

    import app.features.exam_frameworks.tasks as tasks_mod

    monkeypatch.setattr(tasks_mod, "research_framework", _FakeTask, raising=False)

    # Post-commit side effects (notifications + NATS) are covered elsewhere; stub them.
    import app.features.exam_frameworks.notifications as notif_mod
    from app.infrastructure.events import exam_frameworks as events_mod

    monkeypatch.setattr(notif_mod, "notify_platform_admins", _noop)
    monkeypatch.setattr(notif_mod, "notify_version_available", _noop)
    monkeypatch.setattr(events_mod, "publish_framework_event", _noop)


def test_m07_audit_actions_registered() -> None:
    from app.features.audit.actions import M07_AUDIT_ACTIONS, REGISTERED_AUDIT_ACTIONS

    for action in ("framework.created", "framework.approved", "framework.published"):
        assert action in M07_AUDIT_ACTIONS
        assert action in REGISTERED_AUDIT_ACTIONS


@pytest.mark.asyncio
async def test_m07_full_framework_lifecycle_e2e() -> None:
    session: Any = object()
    admin = ExamFrameworkService(session)
    student = StudentFrameworkService(session)

    # 1. Platform Admin creates a DRAFT framework (Punjab, grades 9-10).
    framework = await admin.create_framework(
        ExamFrameworkCreate(
            name="Matric Punjab — Physics",
            exam_target="Matric Punjab Board — Physics",
            subject_slug="physics",
            region="Punjab",
            target_grade_range=[9, 10],
            language="en",
        ),
        actor_id="admin-1",
    )
    assert framework.status == FrameworkStatus.DRAFT

    # A Sindh-only framework that a Punjab student must NOT see (region scoping).
    await admin.create_framework(
        ExamFrameworkCreate(
            name="Matric Sindh — Physics",
            exam_target="Matric Sindh Board — Physics",
            subject_slug="physics",
            region="Sindh",
            target_grade_range=[9, 10],
            language="en",
        ),
        actor_id="admin-1",
    )

    # 2-4. Research -> PENDING_APPROVAL -> approve -> PUBLISHED v1.
    job = await admin.trigger_research(framework.id, actor_id="admin-1")
    assert _Store.frameworks[framework.id].status == FrameworkStatus.RESEARCHING
    status = await admin.run_and_persist_research(framework.id, job.id)
    assert status.value == "succeeded"
    assert _Store.frameworks[framework.id].status == FrameworkStatus.PENDING_APPROVAL
    plan_v1 = await admin.approve_plan(framework.id, actor_id="admin-1")
    assert plan_v1.version == 1
    assert _Store.frameworks[framework.id].status == FrameworkStatus.PUBLISHED

    # Publish the Sindh framework too so both are PUBLISHED (region filter, not status).
    sindh = next(f for f in _Store.frameworks.values() if f.region == "Sindh")
    sindh_job = await admin.trigger_research(sindh.id, actor_id="admin-1")
    await admin.run_and_persist_research(sindh.id, sindh_job.id)
    await admin.approve_plan(sindh.id, actor_id="admin-1")

    # 5. Student browses with region + grade scoping: Punjab grade-10 sees only Punjab.
    available = await student.list_available(region="Punjab", grade=10)
    available_ids = {a.framework.id for a in available}
    assert framework.id in available_ids
    assert sindh.id not in available_ids  # Sindh-only excluded (Acceptance #4)

    # Grade filter: a grade-12 student sees neither (both are grades 9-10).
    assert await student.list_available(region="Punjab", grade=12) == []

    # Student selects -> ACTIVE, pinned to v1.
    selection = await student.select(
        framework.id, SelectionTenantType.SCHOOL, student_user_id="stu-1"
    )
    assert selection.selection.status == SelectionStatus.ACTIVE
    assert selection.selection.pinned_version == 1
    assert selection.update_available is False

    # 6. Plan renders (self-study hook): pinned v1 content is returned.
    fw, plan = await student.get_selection_study_plan(
        selection.selection.id, SelectionTenantType.SCHOOL, "stu-1"
    )
    assert plan.version == 1
    topics_json: Any = plan.content_jsonb["topics"]
    assert topics_json[0]["topic_name"] == "Newton's Laws"

    # 7-9. Quarterly refresh -> v2 -> approve -> PUBLISHED v2 (supersedes v1).
    refresh_job = await admin.trigger_refresh(framework.id, actor_id="system")
    assert _Store.frameworks[framework.id].status == FrameworkStatus.REFRESHING
    await admin.run_and_persist_research(framework.id, refresh_job.id)
    plan_v2 = await admin.approve_plan(framework.id, actor_id="admin-1")
    assert plan_v2.version == 2
    assert _Store.frameworks[framework.id].status == FrameworkStatus.PUBLISHED
    assert _Store.plans[plan_v1.id].status == StudyPlanStatus.SUPERSEDED

    # 10. The v1-pinned student now sees the opt-in switch banner.
    views = await student.list_my_selections(SelectionTenantType.SCHOOL, "stu-1")
    assert len(views) == 1
    assert views[0].selection.pinned_version == 1
    assert views[0].latest_version == 2
    assert views[0].update_available is True  # opt-in banner (Acceptance #5)

    # 11. Student opts in -> pinned bumped to v2 (never auto-switched).
    switched = await student.switch_version(
        selection.selection.id, SelectionTenantType.SCHOOL, "stu-1"
    )
    assert switched.selection.pinned_version == 2
    assert switched.update_available is False
