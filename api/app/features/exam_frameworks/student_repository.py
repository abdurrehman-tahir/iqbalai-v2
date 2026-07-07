"""Student-facing exam-framework repository — browse + select (T-096).

Students (both tenant types) read the platform-shared framework tables directly from
the ``school`` schema — the same precedent as independent onboarding reading
``school.exam_syllabi`` — filtered to what is student-visible (PUBLISHED frameworks,
APPROVED plan versions). Selections are written to ``school.student_framework_selections``
for both tenants; the model is school-qualified, so the write lands there regardless of
the caller's tenant schema (§3.16/§4.21). ``student_user_id`` is a cross-schema app-user
id (plain column, no FK).
"""

from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import not_deleted
from app.features.exam_frameworks.models import (
    ExamFramework,
    FrameworkStatus,
    FrameworkStudyPlan,
    SelectionStatus,
    SelectionTenantType,
    StudentFrameworkSelection,
    StudyPlanStatus,
)

# Region sentinel: a framework tagged "any" is visible to students of every region.
REGION_ANY = "any"


class StudentFrameworkRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_available_frameworks(self, region: str, grade: int) -> list[ExamFramework]:
        """PUBLISHED frameworks a student in ``region``/``grade`` may select.

        Region scoping (Acceptance #2): the framework's region matches the student's
        region OR is "any". Grade scoping (Acceptance #3): the student's grade is within
        the framework's ``target_grade_range``. DEPRECATED/DRAFT are excluded — only
        currently offered frameworks appear.
        """
        stmt = (
            select(ExamFramework)
            .where(
                ExamFramework.status == FrameworkStatus.PUBLISHED,
                not_deleted(ExamFramework),
                or_(ExamFramework.region == region, ExamFramework.region == REGION_ANY),
                # grade ∈ target_grade_range (PG array containment: target @> ARRAY[grade]).
                ExamFramework.target_grade_range.contains([grade]),
            )
            .order_by(ExamFramework.name.asc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_published_framework(self, framework_id: str) -> ExamFramework | None:
        """A framework a student may act on — PUBLISHED only (excludes DEPRECATED/DRAFT)."""
        result = await self._session.execute(
            select(ExamFramework).where(
                ExamFramework.id == framework_id,
                ExamFramework.status == FrameworkStatus.PUBLISHED,
                not_deleted(ExamFramework),
            )
        )
        return result.scalar_one_or_none()

    async def get_current_published_plan(self, framework_id: str) -> FrameworkStudyPlan | None:
        """The current APPROVED plan (highest version) — what a new selection pins to."""
        result = await self._session.execute(
            select(FrameworkStudyPlan)
            .where(
                FrameworkStudyPlan.framework_id == framework_id,
                FrameworkStudyPlan.status == StudyPlanStatus.APPROVED,
            )
            .order_by(FrameworkStudyPlan.version.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_plan_by_version(
        self, framework_id: str, version: int
    ) -> FrameworkStudyPlan | None:
        """A specific plan version (what a selection is pinned to) — for rendering."""
        result = await self._session.execute(
            select(FrameworkStudyPlan).where(
                FrameworkStudyPlan.framework_id == framework_id,
                FrameworkStudyPlan.version == version,
            )
        )
        return result.scalar_one_or_none()

    async def get_framework(self, framework_id: str) -> ExamFramework | None:
        """Any non-deleted framework (incl. deprecated) — for reading an existing selection."""
        result = await self._session.execute(
            select(ExamFramework).where(
                ExamFramework.id == framework_id, not_deleted(ExamFramework)
            )
        )
        return result.scalar_one_or_none()

    async def list_selections(
        self, tenant_type: SelectionTenantType, student_user_id: str
    ) -> list[StudentFrameworkSelection]:
        """A student's selections (both ACTIVE and ABANDONED — history retained)."""
        result = await self._session.execute(
            select(StudentFrameworkSelection)
            .where(
                StudentFrameworkSelection.tenant_type == tenant_type,
                StudentFrameworkSelection.student_user_id == student_user_id,
                not_deleted(StudentFrameworkSelection),
            )
            .order_by(StudentFrameworkSelection.selected_at.desc())
        )
        return list(result.scalars().all())

    async def get_active_selection(
        self, tenant_type: SelectionTenantType, student_user_id: str, framework_id: str
    ) -> StudentFrameworkSelection | None:
        """An existing ACTIVE selection of this framework by this student, if any."""
        result = await self._session.execute(
            select(StudentFrameworkSelection).where(
                StudentFrameworkSelection.tenant_type == tenant_type,
                StudentFrameworkSelection.student_user_id == student_user_id,
                StudentFrameworkSelection.framework_id == framework_id,
                StudentFrameworkSelection.status == SelectionStatus.ACTIVE,
                not_deleted(StudentFrameworkSelection),
            )
        )
        return result.scalar_one_or_none()

    async def list_active_selections_pinned_below(
        self, framework_id: str, version: int
    ) -> list[StudentFrameworkSelection]:
        """ACTIVE selections of a framework pinned to an older version than ``version``.

        Recipients for the ``framework.version_available`` notification when a refreshed
        (v2+) plan is approved (T-097 Acceptance #3).
        """
        result = await self._session.execute(
            select(StudentFrameworkSelection).where(
                StudentFrameworkSelection.framework_id == framework_id,
                StudentFrameworkSelection.status == SelectionStatus.ACTIVE,
                StudentFrameworkSelection.pinned_version < version,
                not_deleted(StudentFrameworkSelection),
            )
        )
        return list(result.scalars().all())

    async def get_selection_by_id(self, selection_id: str) -> StudentFrameworkSelection | None:
        result = await self._session.execute(
            select(StudentFrameworkSelection).where(
                StudentFrameworkSelection.id == selection_id,
                not_deleted(StudentFrameworkSelection),
            )
        )
        return result.scalar_one_or_none()

    def add(self, selection: StudentFrameworkSelection) -> None:
        self._session.add(selection)

    async def commit(self) -> None:
        await self._session.commit()

    async def refresh(self, selection: StudentFrameworkSelection) -> None:
        await self._session.refresh(selection)
