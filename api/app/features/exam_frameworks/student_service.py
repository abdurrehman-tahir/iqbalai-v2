"""Student-facing exam-framework service — selection + rendering (T-096).

Students browse published frameworks (region + grade scoped), select one or more
(each pins to the current published version), see the §3.5.2 plan rendered, opt in to a
refreshed version (T-095 banner), or drop a selection (kept as ABANDONED so history is
retained). Serves both tenant types: the caller's ``tenant_type`` (JWT claim) is stamped
on the selection and the app user id is resolved per tenant.

Self-Study hook: ``get_selection_study_plan`` exposes the structured plan for the future
Flow 8 self-study planner (M-08+). The Lecture Mode "exam prep track" overlay is a
documented hook only here (UI deferred to M-09+).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, PreconditionFailedError
from app.features.exam_frameworks.models import (
    ExamFramework,
    FrameworkStudyPlan,
    SelectionStatus,
    SelectionTenantType,
    StudentFrameworkSelection,
)
from app.features.exam_frameworks.student_repository import StudentFrameworkRepository
from app.features.independent_users.repository import IndependentUserRepository
from app.features.users.repository import UserRepository

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class AvailableFramework:
    """A selectable framework plus its current published version (view model)."""

    framework: ExamFramework
    current_version: int


@dataclass(frozen=True)
class SelectionView:
    """A student's selection plus the latest published version (for the switch banner)."""

    selection: StudentFrameworkSelection
    framework: ExamFramework
    latest_version: int

    @property
    def update_available(self) -> bool:
        # Opt-in switch banner (T-095): a newer approved version exists beyond the pin.
        return (
            self.selection.status == SelectionStatus.ACTIVE
            and self.latest_version > self.selection.pinned_version
        )


class StudentFrameworkService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = StudentFrameworkRepository(session)

    async def resolve_student(self, claims: dict[str, object]) -> tuple[SelectionTenantType, str]:
        """Map JWT claims to (tenant_type, app-user-id) for stamping a selection.

        The selection's ``student_user_id`` is the app user id (not the Authentik sub),
        resolved per tenant — consistent with the rest of the student surface.
        """
        tenant_raw = str(claims.get("tenant_type", "school"))
        sub = str(claims.get("sub", ""))
        if tenant_raw == "independent":
            ind = await IndependentUserRepository(self._session).get_by_authentik_id(sub)
            if ind is None:
                raise NotFoundError("Independent student account not found")
            return SelectionTenantType.INDEPENDENT, ind.id
        user = await UserRepository(self._session).get_by_authentik_id(sub)
        if user is None:
            raise NotFoundError("Student account not found")
        return SelectionTenantType.SCHOOL, user.id

    async def list_available(self, region: str, grade: int) -> list[AvailableFramework]:
        frameworks = await self._repo.list_available_frameworks(region, grade)
        out: list[AvailableFramework] = []
        for framework in frameworks:
            plan = await self._repo.get_current_published_plan(framework.id)
            # A PUBLISHED framework always has an APPROVED plan; skip defensively if not.
            if plan is None:
                continue
            out.append(AvailableFramework(framework=framework, current_version=plan.version))
        return out

    async def select(
        self, framework_id: str, tenant_type: SelectionTenantType, student_user_id: str
    ) -> SelectionView:
        """Select a framework -> ACTIVE, pinned to the current version (Acceptance #1).

        Multiple *different* frameworks per student are allowed (Acceptance #4); a second
        ACTIVE selection of the *same* framework is rejected. Only PUBLISHED frameworks
        are selectable — DEPRECATED ones are not offered to new students (T-095).
        """
        framework = await self._repo.get_published_framework(framework_id)
        if framework is None:
            raise NotFoundError(f"Framework '{framework_id}' is not available for selection")
        plan = await self._repo.get_current_published_plan(framework_id)
        if plan is None:
            raise PreconditionFailedError(
                f"Framework '{framework_id}' has no published study plan yet"
            )
        existing = await self._repo.get_active_selection(tenant_type, student_user_id, framework_id)
        if existing is not None:
            raise ConflictError("You have already selected this framework")

        selection = StudentFrameworkSelection(
            tenant_type=tenant_type,
            student_user_id=student_user_id,
            framework_id=framework_id,
            pinned_version=plan.version,
            status=SelectionStatus.ACTIVE,
            selected_at=datetime.now(timezone.utc),
        )
        self._repo.add(selection)
        await self._repo.commit()
        await self._repo.refresh(selection)
        logger.info(
            "framework_selected",
            framework_id=framework_id,
            tenant_type=tenant_type.value,
            version=plan.version,
        )
        return SelectionView(selection=selection, framework=framework, latest_version=plan.version)

    async def list_my_selections(
        self, tenant_type: SelectionTenantType, student_user_id: str
    ) -> list[SelectionView]:
        selections = await self._repo.list_selections(tenant_type, student_user_id)
        views: list[SelectionView] = []
        for selection in selections:
            framework = await self._repo.get_framework(selection.framework_id)
            if framework is None:
                continue
            latest_plan = await self._repo.get_current_published_plan(selection.framework_id)
            latest_version = (
                latest_plan.version if latest_plan is not None else selection.pinned_version
            )
            views.append(
                SelectionView(
                    selection=selection, framework=framework, latest_version=latest_version
                )
            )
        return views

    async def get_selection_study_plan(
        self, selection_id: str, tenant_type: SelectionTenantType, student_user_id: str
    ) -> tuple[ExamFramework, FrameworkStudyPlan]:
        """The pinned study-plan version for a selection, rendered (Acceptance #5).

        Also the self-study integration hook (Acceptance #6): the structured plan is
        returned for the future Flow 8 planner.
        """
        selection = await self._owned_selection(selection_id, tenant_type, student_user_id)
        framework = await self._repo.get_framework(selection.framework_id)
        if framework is None:
            raise NotFoundError("Framework no longer exists")
        plan = await self._repo.get_plan_by_version(
            selection.framework_id, selection.pinned_version
        )
        if plan is None:
            raise NotFoundError("Pinned study-plan version not found")
        return framework, plan

    async def switch_version(
        self, selection_id: str, tenant_type: SelectionTenantType, student_user_id: str
    ) -> SelectionView:
        """Opt in to the latest published version (Acceptance #2, §3.5.3).

        Never auto-switched — the student chooses this. Bumps the pin in place; historical
        progress is retained (same ACTIVE row). No-op if already on the latest.
        """
        selection = await self._owned_selection(selection_id, tenant_type, student_user_id)
        if selection.status != SelectionStatus.ACTIVE:
            raise ConflictError("Only an active selection can be switched")
        framework = await self._repo.get_framework(selection.framework_id)
        if framework is None:
            raise NotFoundError("Framework no longer exists")
        latest_plan = await self._repo.get_current_published_plan(selection.framework_id)
        if latest_plan is None:
            raise PreconditionFailedError("No published version to switch to")
        if latest_plan.version > selection.pinned_version:
            selection.pinned_version = latest_plan.version
            await self._repo.commit()
            await self._repo.refresh(selection)
            logger.info(
                "framework_selection_switched",
                selection_id=selection_id,
                version=latest_plan.version,
            )
        return SelectionView(
            selection=selection, framework=framework, latest_version=latest_plan.version
        )

    async def drop(
        self, selection_id: str, tenant_type: SelectionTenantType, student_user_id: str
    ) -> SelectionView:
        """Drop a selection -> ABANDONED (Acceptance #7).

        The row is retained (not hard-deleted) so historical progress is preserved.
        """
        selection = await self._owned_selection(selection_id, tenant_type, student_user_id)
        framework = await self._repo.get_framework(selection.framework_id)
        if framework is None:
            raise NotFoundError("Framework no longer exists")
        if selection.status != SelectionStatus.ABANDONED:
            selection.status = SelectionStatus.ABANDONED
            await self._repo.commit()
            await self._repo.refresh(selection)
            logger.info("framework_selection_dropped", selection_id=selection_id)
        latest_plan = await self._repo.get_current_published_plan(selection.framework_id)
        latest_version = (
            latest_plan.version if latest_plan is not None else selection.pinned_version
        )
        return SelectionView(
            selection=selection, framework=framework, latest_version=latest_version
        )

    async def _owned_selection(
        self, selection_id: str, tenant_type: SelectionTenantType, student_user_id: str
    ) -> StudentFrameworkSelection:
        """Fetch a selection, 404 unless it belongs to the calling student."""
        selection = await self._repo.get_selection_by_id(selection_id)
        if (
            selection is None
            or selection.tenant_type != tenant_type
            or selection.student_user_id != student_user_id
        ):
            raise NotFoundError(f"Selection '{selection_id}' not found")
        return selection
