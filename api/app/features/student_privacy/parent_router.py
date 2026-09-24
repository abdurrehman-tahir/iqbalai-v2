"""Minimal parent read path for linked child's lecture questions — T-162.

Full parent lecture surface is Flow 10 / M-19. This endpoint exists so #72
opt-out can be enforced on a concrete parent read API before Flow 10 ships.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db, require_role
from app.core.exceptions import PermissionDeniedError
from app.core.responses import SuccessEnvelope, success
from app.features.parent_child_links.service import ParentChildLinkService
from app.features.student_privacy.service import student_allows_teacher_share
from app.features.student_questions.models import (
    SchoolStudentQuestion,
    SchoolStudentQuestionConversation,
)
from app.features.student_questions.repository import (
    StudentQuestionConversationRepository,
    StudentQuestionRepository,
)
from app.features.student_questions.schemas import StudentQuestionRead
from app.features.student_questions.service import question_to_read

router = APIRouter(prefix="/parents/me", tags=["parent-lecture-questions"])


@router.get(
    "/students/{student_user_id}/lecture-questions",
    response_model=SuccessEnvelope[list[StudentQuestionRead]],
    operation_id="parent_list_student_lecture_questions",
    summary="Read-only lecture questions for a linked child (respects #72)",
    dependencies=[require_role("parent")],
)
async def list_student_lecture_questions(
    student_user_id: str,
    lecture_id: str | None = Query(default=None),
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Return the child's lecture questions only when #72 = share.

    When the student has opted out (private), returns an empty list so parents
    cannot observe individual Q&A (INVIOLATE). Requires an approved link.
    """
    access = await ParentChildLinkService(db).get_parent_student_access_state(
        student_user_id, claims
    )
    if not access.read_only_access:
        raise PermissionDeniedError("No approved parent-child link for this student")

    if not await student_allows_teacher_share(db, student_user_id):
        return success([])

    questions_repo = StudentQuestionRepository(db)
    conversations_repo = StudentQuestionConversationRepository(db)

    if lecture_id:
        questions = await questions_repo.list_for_student_lecture(
            student_user_id=student_user_id, lecture_id=lecture_id
        )
    else:
        result = await db.execute(
            select(SchoolStudentQuestion)
            .where(SchoolStudentQuestion.student_user_id == student_user_id)
            .order_by(SchoolStudentQuestion.asked_at.desc())
            .limit(100)
        )
        questions = list(result.scalars().all())

    turns = await conversations_repo.list_for_questions([q.id for q in questions])
    by_root: dict[str, list[SchoolStudentQuestionConversation]] = defaultdict(list)
    for turn in turns:
        by_root[turn.root_question_id].append(turn)

    return success(
        [question_to_read(q, by_root.get(q.id, [])).model_dump(mode="json") for q in questions]
    )
