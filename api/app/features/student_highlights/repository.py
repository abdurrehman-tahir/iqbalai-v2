"""Persistence for student highlights + flashcards (T-185 / T-186 / T-188)."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import not_deleted
from app.features.lectures.models import SchoolLecture
from app.features.student_highlights.models import SchoolStudentFlashcard, SchoolStudentHighlight


@dataclass(frozen=True)
class LectureHighlightAggregate:
    """Anonymous per-lecture counts for Coordinator/Admin (T-188, §6.19)."""

    lecture_id: str
    highlight_count: int
    student_count: int
    flashcard_count: int
    top_concepts: list[tuple[str, int]]


class StudentHighlightRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, row: SchoolStudentHighlight) -> SchoolStudentHighlight:
        self._session.add(row)
        await self._session.flush()
        return row

    async def get_by_question_id(self, question_id: str) -> SchoolStudentHighlight | None:
        result = await self._session.execute(
            select(SchoolStudentHighlight).where(
                SchoolStudentHighlight.question_id == question_id,
                not_deleted(SchoolStudentHighlight),
            )
        )
        return result.scalars().first()

    async def get_owned(
        self, *, highlight_id: str, student_user_id: str
    ) -> SchoolStudentHighlight | None:
        result = await self._session.execute(
            select(SchoolStudentHighlight).where(
                SchoolStudentHighlight.id == highlight_id,
                SchoolStudentHighlight.student_user_id == student_user_id,
                not_deleted(SchoolStudentHighlight),
            )
        )
        return result.scalars().first()

    async def list_for_student_lecture(
        self, *, student_user_id: str, lecture_id: str
    ) -> list[SchoolStudentHighlight]:
        """Owner-scoped: rows of *this* student only, never other students'."""
        result = await self._session.execute(
            select(SchoolStudentHighlight)
            .where(
                SchoolStudentHighlight.student_user_id == student_user_id,
                SchoolStudentHighlight.lecture_id == lecture_id,
                not_deleted(SchoolStudentHighlight),
            )
            .order_by(SchoolStudentHighlight.created_at.asc())
        )
        return list(result.scalars().all())

    async def list_for_student_with_lectures(
        self, *, student_user_id: str, limit: int, offset: int
    ) -> list[tuple[SchoolStudentHighlight, SchoolLecture]]:
        """My Highlights feed: newest first, joined to (non-deleted) lectures."""
        result = await self._session.execute(
            select(SchoolStudentHighlight, SchoolLecture)
            .join(SchoolLecture, SchoolLecture.id == SchoolStudentHighlight.lecture_id)
            .where(
                SchoolStudentHighlight.student_user_id == student_user_id,
                not_deleted(SchoolStudentHighlight),
                not_deleted(SchoolLecture),
            )
            .order_by(SchoolStudentHighlight.created_at.desc(), SchoolStudentHighlight.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return [(row[0], row[1]) for row in result.all()]

    async def count_for_student(self, *, student_user_id: str) -> int:
        result = await self._session.execute(
            select(func.count())
            .select_from(SchoolStudentHighlight)
            .join(SchoolLecture, SchoolLecture.id == SchoolStudentHighlight.lecture_id)
            .where(
                SchoolStudentHighlight.student_user_id == student_user_id,
                not_deleted(SchoolStudentHighlight),
                not_deleted(SchoolLecture),
            )
        )
        return int(result.scalar_one())

    async def aggregate_for_lecture(
        self, *, lecture_id: str, student_ids: list[str] | None
    ) -> LectureHighlightAggregate:
        """Counts only — no text, no per-student rows. ``student_ids`` limits the
        population (e.g. to students who share activity, #72); ``None`` = all."""
        hl_filter = [
            SchoolStudentHighlight.lecture_id == lecture_id,
            not_deleted(SchoolStudentHighlight),
        ]
        fc_filter = [
            SchoolStudentFlashcard.lecture_id == lecture_id,
            not_deleted(SchoolStudentFlashcard),
        ]
        if student_ids is not None:
            hl_filter.append(SchoolStudentHighlight.student_user_id.in_(student_ids))
            fc_filter.append(SchoolStudentFlashcard.student_user_id.in_(student_ids))
        counts = (
            await self._session.execute(
                select(
                    func.count(SchoolStudentHighlight.id),
                    func.count(distinct(SchoolStudentHighlight.student_user_id)),
                ).where(*hl_filter)
            )
        ).one()
        cards = (
            await self._session.execute(
                select(func.count(SchoolStudentFlashcard.id)).where(*fc_filter)
            )
        ).scalar_one()
        concepts = (
            await self._session.execute(
                select(SchoolStudentHighlight.concept_tag, func.count())
                .where(*hl_filter, SchoolStudentHighlight.concept_tag.is_not(None))
                .group_by(SchoolStudentHighlight.concept_tag)
                .order_by(func.count().desc(), SchoolStudentHighlight.concept_tag.asc())
                .limit(5)
            )
        ).all()
        return LectureHighlightAggregate(
            lecture_id=lecture_id,
            highlight_count=int(counts[0]),
            student_count=int(counts[1]),
            flashcard_count=int(cards),
            top_concepts=[(str(c), int(n)) for c, n in concepts],
        )


class StudentFlashcardRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def live_by_hashes(
        self, *, student_user_id: str, dedupe_hashes: list[str]
    ) -> dict[str, SchoolStudentFlashcard]:
        if not dedupe_hashes:
            return {}
        result = await self._session.execute(
            select(SchoolStudentFlashcard).where(
                SchoolStudentFlashcard.student_user_id == student_user_id,
                SchoolStudentFlashcard.dedupe_hash.in_(dedupe_hashes),
                not_deleted(SchoolStudentFlashcard),
            )
        )
        return {c.dedupe_hash: c for c in result.scalars().all()}

    async def get_owned(
        self, *, flashcard_id: str, student_user_id: str
    ) -> SchoolStudentFlashcard | None:
        result = await self._session.execute(
            select(SchoolStudentFlashcard).where(
                SchoolStudentFlashcard.id == flashcard_id,
                SchoolStudentFlashcard.student_user_id == student_user_id,
                not_deleted(SchoolStudentFlashcard),
            )
        )
        return result.scalars().first()
