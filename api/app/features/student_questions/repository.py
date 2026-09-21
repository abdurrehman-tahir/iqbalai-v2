"""Persistence for student questions + conversation turns (school)."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.lectures.models import SchoolLectureParagraph
from app.features.student_questions.models import (
    SchoolStudentQuestion,
    SchoolStudentQuestionConversation,
)


class StudentQuestionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, question_id: str) -> SchoolStudentQuestion | None:
        return await self._session.get(SchoolStudentQuestion, question_id)

    async def create(self, row: SchoolStudentQuestion) -> SchoolStudentQuestion:
        self._session.add(row)
        await self._session.flush()
        return row

    async def save(self, row: SchoolStudentQuestion) -> SchoolStudentQuestion:
        await self._session.flush()
        return row

    async def list_for_student_lecture(
        self, *, student_user_id: str, lecture_id: str
    ) -> list[SchoolStudentQuestion]:
        result = await self._session.execute(
            select(SchoolStudentQuestion)
            .where(
                SchoolStudentQuestion.student_user_id == student_user_id,
                SchoolStudentQuestion.lecture_id == lecture_id,
            )
            .order_by(SchoolStudentQuestion.asked_at.desc())
        )
        return list(result.scalars().all())

    async def count_for_session(self, session_id: str) -> int:
        result = await self._session.execute(
            select(func.count())
            .select_from(SchoolStudentQuestion)
            .where(SchoolStudentQuestion.session_id == session_id)
        )
        return int(result.scalar_one())

    async def count_highlights_for_session(self, session_id: str) -> int:
        result = await self._session.execute(
            select(func.count())
            .select_from(SchoolStudentQuestion)
            .where(
                SchoolStudentQuestion.session_id == session_id,
                SchoolStudentQuestion.highlight_text.is_not(None),
                SchoolStudentQuestion.highlight_text != "",
            )
        )
        return int(result.scalar_one())


class StudentQuestionConversationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self, row: SchoolStudentQuestionConversation
    ) -> SchoolStudentQuestionConversation:
        self._session.add(row)
        await self._session.flush()
        return row

    async def list_for_question(
        self, root_question_id: str
    ) -> list[SchoolStudentQuestionConversation]:
        result = await self._session.execute(
            select(SchoolStudentQuestionConversation)
            .where(SchoolStudentQuestionConversation.root_question_id == root_question_id)
            .order_by(SchoolStudentQuestionConversation.turn_index.asc())
        )
        return list(result.scalars().all())

    async def list_for_questions(
        self, root_question_ids: list[str]
    ) -> list[SchoolStudentQuestionConversation]:
        if not root_question_ids:
            return []
        result = await self._session.execute(
            select(SchoolStudentQuestionConversation)
            .where(SchoolStudentQuestionConversation.root_question_id.in_(root_question_ids))
            .order_by(
                SchoolStudentQuestionConversation.root_question_id.asc(),
                SchoolStudentQuestionConversation.turn_index.asc(),
            )
        )
        return list(result.scalars().all())

    async def next_turn_index(self, root_question_id: str) -> int:
        result = await self._session.execute(
            select(func.coalesce(func.max(SchoolStudentQuestionConversation.turn_index), -1)).where(
                SchoolStudentQuestionConversation.root_question_id == root_question_id
            )
        )
        current = int(result.scalar_one())
        return current + 1


class LectureParagraphLookup:
    """Thin paragraph fetch for content-element tagging (T-156)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, paragraph_id: str) -> SchoolLectureParagraph | None:
        return await self._session.get(SchoolLectureParagraph, paragraph_id)
