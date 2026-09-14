"""Admin comparative teacher metrics — raw query layer (T-139, #38).

School-tenant only, same as benchmarking (§Flow 5 §3.11 #37). Unlike the
anonymized benchmark, this surface is admin-facing and shows real teacher
names/schools — scope is enforced by the caller (service layer), not here.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.grades.models import Grade
from app.features.lectures.models import SchoolLecture, SchoolLectureVersion
from app.features.offerings.models import GradeSubjectOffering
from app.features.schools.models import School
from app.features.subjects.models import Subject
from app.features.users.models import User


@dataclass(frozen=True)
class TeacherMetricsRow:
    """One scored lecture version, joined out to every dimension admins can
    filter/sort by."""

    teacher_user_id: str
    teacher_name: str
    school_id: str
    school_name: str
    subject_id: str
    subject_name: str
    grade_level_ordinal: str
    lecture_id: str
    scores_jsonb: dict[str, object]
    topic_relevance_pct: float | None


class AdminTeacherMetricsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_scored_versions(
        self, *, school_ids: list[str] | None
    ) -> list[TeacherMetricsRow]:
        """Every scored lecture version in scope, joined to teacher/school/subject/
        grade. ``school_ids=None`` means unrestricted (Platform Admin)."""
        stmt = (
            select(
                SchoolLecture.teacher_user_id,
                User.display_name,
                SchoolLecture.school_id,
                School.name,
                GradeSubjectOffering.subject_id,
                Subject.name,
                Grade.level_ordinal,
                SchoolLecture.id,
                SchoolLectureVersion.scores_jsonb,
                SchoolLectureVersion.topic_relevance_pct,
            )
            .select_from(SchoolLectureVersion)
            .join(SchoolLecture, SchoolLecture.id == SchoolLectureVersion.lecture_id)
            .join(
                GradeSubjectOffering,
                GradeSubjectOffering.id == SchoolLecture.grade_subject_offering_id,
            )
            .join(Grade, Grade.id == GradeSubjectOffering.grade_id)
            .join(Subject, Subject.id == GradeSubjectOffering.subject_id)
            .join(School, School.id == SchoolLecture.school_id)
            .join(User, User.id == SchoolLecture.teacher_user_id)
            .where(SchoolLectureVersion.scores_jsonb.is_not(None))
        )
        if school_ids is not None:
            stmt = stmt.where(SchoolLecture.school_id.in_(school_ids))

        result = await self._session.execute(stmt)
        rows: list[TeacherMetricsRow] = []
        for (
            teacher_user_id,
            teacher_name,
            school_id,
            school_name,
            subject_id,
            subject_name,
            level_ordinal,
            lecture_id,
            scores_jsonb,
            topic_relevance_pct,
        ) in result.all():
            if teacher_user_id is None or school_id is None or not isinstance(scores_jsonb, dict):
                continue
            rows.append(
                TeacherMetricsRow(
                    teacher_user_id=teacher_user_id,
                    teacher_name=teacher_name,
                    school_id=school_id,
                    school_name=school_name,
                    subject_id=subject_id,
                    subject_name=subject_name,
                    grade_level_ordinal=str(level_ordinal),
                    lecture_id=lecture_id,
                    scores_jsonb=scores_jsonb,
                    topic_relevance_pct=(
                        float(topic_relevance_pct) if topic_relevance_pct is not None else None
                    ),
                )
            )
        return rows

    async def list_school_ids_for_district(self, district_id: str) -> list[str]:
        result = await self._session.execute(
            select(School.id).where(School.district_id == district_id)
        )
        return list(result.scalars().all())
