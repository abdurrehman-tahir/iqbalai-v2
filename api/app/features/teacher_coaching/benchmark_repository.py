"""Teacher-benchmark repository — T-139 (Flow 5 §3.11 #37).

Isolates the raw cross-table joins so ``benchmark_service.py`` stays pure
orchestration logic, testable with a fake repository (this codebase's
convention — see ``SchoolTeacherAiMemoryRepository``/its tests; no service
in this repo runs a raw multi-join ``select`` directly against a session).
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.grades.models import Grade
from app.features.lectures.models import SchoolLecture, SchoolLectureVersion
from app.features.offerings.models import GradeSubjectOffering
from app.features.subjects.models import Subject
from app.features.teacher_coaching.models import SchoolTeacherBenchmark
from app.features.teacher_onboarding.models import TeacherProfile


@dataclass(frozen=True)
class ScoredVersionRow:
    """One scored lecture version, joined out to its cohort dimensions."""

    teacher_user_id: str
    subject_id: str
    grade_level_ordinal: str
    region: str
    scores_jsonb: dict[str, object]


class SchoolTeacherBenchmarkRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_scored_versions(self) -> list[ScoredVersionRow]:
        """Every scored lecture version, joined to (subject, grade, region) —
        the raw material the weekly cohort recompute groups and ranks."""
        result = await self._session.execute(
            select(
                SchoolLecture.teacher_user_id,
                GradeSubjectOffering.subject_id,
                Grade.level_ordinal,
                TeacherProfile.region_province,
                SchoolLectureVersion.scores_jsonb,
            )
            .select_from(SchoolLectureVersion)
            .join(SchoolLecture, SchoolLecture.id == SchoolLectureVersion.lecture_id)
            .join(
                GradeSubjectOffering,
                GradeSubjectOffering.id == SchoolLecture.grade_subject_offering_id,
            )
            .join(Grade, Grade.id == GradeSubjectOffering.grade_id)
            .join(TeacherProfile, TeacherProfile.user_id == SchoolLecture.teacher_user_id)
            .where(SchoolLectureVersion.scores_jsonb.is_not(None))
        )
        return [
            ScoredVersionRow(
                teacher_user_id=teacher_user_id,
                subject_id=subject_id,
                grade_level_ordinal=str(level_ordinal),
                region=region,
                scores_jsonb=scores_jsonb,
            )
            for teacher_user_id, subject_id, level_ordinal, region, scores_jsonb in result.all()
            if teacher_user_id is not None and isinstance(scores_jsonb, dict)
        ]

    async def list_all(self) -> list[SchoolTeacherBenchmark]:
        result = await self._session.execute(select(SchoolTeacherBenchmark))
        return list(result.scalars().all())

    async def list_for_teacher_with_subject_name(
        self, teacher_user_id: str
    ) -> list[tuple[SchoolTeacherBenchmark, str]]:
        result = await self._session.execute(
            select(SchoolTeacherBenchmark, Subject.name)
            .join(Subject, Subject.id == SchoolTeacherBenchmark.subject_id)
            .where(
                SchoolTeacherBenchmark.teacher_user_id == teacher_user_id,
                SchoolTeacherBenchmark.opted_out.is_(False),
                SchoolTeacherBenchmark.percentile.is_not(None),
            )
            .order_by(SchoolTeacherBenchmark.updated_at.desc())
        )
        return [(row, subject_name) for row, subject_name in result.all()]

    async def list_all_for_teacher(self, teacher_user_id: str) -> list[SchoolTeacherBenchmark]:
        result = await self._session.execute(
            select(SchoolTeacherBenchmark).where(
                SchoolTeacherBenchmark.teacher_user_id == teacher_user_id
            )
        )
        return list(result.scalars().all())

    def add(self, row: SchoolTeacherBenchmark) -> None:
        self._session.add(row)

    async def commit(self) -> None:
        await self._session.commit()

    async def get_subject_names(self, subject_ids: list[str]) -> dict[str, str]:
        """Bulk subject-name lookup for the weekly beat's notification fan-out
        — one query for every subject touched, instead of N+1 per teacher."""
        if not subject_ids:
            return {}
        result = await self._session.execute(
            select(Subject.id, Subject.name).where(Subject.id.in_(subject_ids))
        )
        return {subject_id: name for subject_id, name in result.all()}
