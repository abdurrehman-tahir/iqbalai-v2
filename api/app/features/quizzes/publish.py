"""Quiz publish helpers bound to lecture publication (T-145 / T-142 hook)."""

from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.quizzes.models import QuizAssignmentStatus, SchoolQuiz, SchoolQuizAssignment


async def publish_pending_assignments_for_lecture(
    session: AsyncSession, *, lecture_id: str
) -> int:
    """Flip ``pending`` → ``published`` for all quiz assignments of a lecture.

    Called from lecture publish (T-142). Returns the number of rows updated.
    No-op when no quizzes exist yet (generation may still be in flight).
    """
    quiz_ids = (
        await session.execute(
            select(SchoolQuiz.id).where(
                SchoolQuiz.lecture_id == lecture_id,
                SchoolQuiz.deleted_at.is_(None),
            )
        )
    ).scalars().all()
    if not quiz_ids:
        return 0

    result = await session.execute(
        update(SchoolQuizAssignment)
        .where(SchoolQuizAssignment.quiz_id.in_(list(quiz_ids)))
        .where(SchoolQuizAssignment.status == QuizAssignmentStatus.PENDING)
        .where(SchoolQuizAssignment.deleted_at.is_(None))
        .values(status=QuizAssignmentStatus.PUBLISHED)
    )
    return int(result.rowcount or 0)
