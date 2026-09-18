"""Exam framework overlay for lecture generation — T-120 (Flow 4 v3 §3.5.4).

Additive (never replacement) context: if any actively-enrolled student in the
lecture's Grade has selected a PUBLISHED Exam Framework relevant to the
lecture's Subject and covering that Grade, the framework's exam_strategy plus
its highest-priority topics are surfaced to the LLM as supplementary
exam-readiness context. Curriculum stays the primary driver of the lecture.

Per §3.2's Custom Persona rule: this overlay is class-wide, never per-student —
it never reads or injects any individual student's persona.
"""

from __future__ import annotations

import re

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.exam_frameworks.models import (
    ExamFramework,
    FrameworkStatus,
    FrameworkStudyPlan,
    SelectionStatus,
    StudentFrameworkSelection,
    StudyPlanStatus,
)
from app.features.exam_frameworks.schemas import FrameworkStudyPlanContent
from app.features.grades.models import Grade
from app.features.student_enrollments.models import StudentEnrollment, StudentEnrollmentStatus

_TOP_PRIORITY_TOPICS = 5
_SLUG_COLLAPSE_RE = re.compile(r"[^a-z0-9]+")


class ExamOverlayContext(BaseModel):
    """Rendered exam-framework context for the lecture prompt (T-120)."""

    framework_name: str
    exam_strategy_summary: str
    priority_topics: list[str]


def normalize_subject_slug(subject_name: str) -> str:
    """``"Physics"`` -> ``"physics"``; ``"General Science"`` -> ``"general-science"``.

    Must produce the same kebab-case format ``ExamFramework.subject_slug`` is
    validated against (app/features/exam_frameworks/schemas.py) — `Subject` rows
    are school-scoped free text (no controlled vocabulary of their own), so this
    normalization is how the two sides are compared, not a stored column.
    """
    return _SLUG_COLLAPSE_RE.sub("-", subject_name.strip().lower()).strip("-")


async def get_exam_framework_overlay(
    session: AsyncSession,
    *,
    grade_id: str,
    subject_name: str,
) -> ExamOverlayContext | None:
    """Additive exam-readiness context, or ``None`` if no relevant framework applies.

    ``None`` whenever: no actively-enrolled students in the grade, none of them
    have an active framework selection, no selected framework is PUBLISHED +
    relevant to this subject + covers this grade, or it has no APPROVED study
    plan yet.
    """
    subject_slug = normalize_subject_slug(subject_name)

    enrolled = await session.execute(
        select(StudentEnrollment.student_user_id).where(
            StudentEnrollment.grade_id == grade_id,
            StudentEnrollment.status == StudentEnrollmentStatus.ACTIVE,
        )
    )
    student_ids = [row[0] for row in enrolled.all()]
    if not student_ids:
        return None

    selected = await session.execute(
        select(StudentFrameworkSelection.framework_id)
        .where(
            StudentFrameworkSelection.student_user_id.in_(student_ids),
            StudentFrameworkSelection.status == SelectionStatus.ACTIVE,
        )
        .distinct()
    )
    framework_ids = [row[0] for row in selected.all()]
    if not framework_ids:
        return None

    grade = await session.get(Grade, grade_id)
    grade_ordinal = grade.level_ordinal if grade is not None else None

    candidates = await session.execute(
        select(ExamFramework)
        .where(
            ExamFramework.id.in_(framework_ids),
            ExamFramework.subject_slug == subject_slug,
            ExamFramework.status == FrameworkStatus.PUBLISHED,
            ExamFramework.deleted_at.is_(None),
        )
        .order_by(ExamFramework.created_at.asc())
    )
    framework = next(
        (
            f
            for f in candidates.scalars().all()
            if grade_ordinal is not None and grade_ordinal in f.target_grade_range
        ),
        None,
    )
    if framework is None:
        return None

    plan_result = await session.execute(
        select(FrameworkStudyPlan)
        .where(
            FrameworkStudyPlan.framework_id == framework.id,
            FrameworkStudyPlan.status == StudyPlanStatus.APPROVED,
        )
        .order_by(FrameworkStudyPlan.version.desc())
        .limit(1)
    )
    plan = plan_result.scalars().first()
    if plan is None:
        return None

    content = FrameworkStudyPlanContent.model_validate(plan.content_jsonb)
    ranked_topics = sorted(content.topics, key=lambda t: t.priority_weight, reverse=True)
    priority_topics = [
        f"{t.topic_name} (priority {t.priority_weight:.1f})"
        for t in ranked_topics[:_TOP_PRIORITY_TOPICS]
    ]
    strategy_summary = " ".join(
        part
        for part in (content.exam_strategy.time_allocation, content.exam_strategy.scoring_strategy)
        if part
    )

    return ExamOverlayContext(
        framework_name=framework.name,
        exam_strategy_summary=strategy_summary,
        priority_topics=priority_topics,
    )
