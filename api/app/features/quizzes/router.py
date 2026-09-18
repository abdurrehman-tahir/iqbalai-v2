"""Quiz HTTP API — student attempt + teacher results (T-145–T-147)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db, require_role
from app.core.responses import SuccessEnvelope, success
from app.features.quizzes.api_schemas import (
    QuizAttemptResultRead,
    QuizOfferingAggregateRead,
    QuizSubmitRequest,
    StudentQuizCardRead,
    StudentQuizDetailRead,
    TeacherStudentQuizResultRead,
)
from app.features.quizzes.service import QuizService

student_router = APIRouter(prefix="/students/me/quizzes", tags=["student-quizzes"])
teacher_router = APIRouter(prefix="/teachers/me/lectures", tags=["teacher-quiz-results"])


@student_router.get(
    "",
    response_model=SuccessEnvelope[list[StudentQuizCardRead]],
    operation_id="student_list_my_quizzes",
    summary="List the authenticated student's published quizzes (T-145)",
    dependencies=[require_role("student")],
)
async def list_my_quizzes(
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    rows = await QuizService(db).list_my_quizzes(claims)
    return success([r.model_dump(mode="json") for r in rows])


@student_router.get(
    "/{assignment_id}",
    response_model=SuccessEnvelope[StudentQuizDetailRead],
    operation_id="student_get_my_quiz",
    summary="Open one of the student's quizzes (T-145/T-146)",
    dependencies=[require_role("student")],
)
async def get_my_quiz(
    assignment_id: str,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    result = await QuizService(db).get_my_quiz(claims, assignment_id)
    return success(result.model_dump(mode="json"))


@student_router.post(
    "/{assignment_id}/submit",
    response_model=SuccessEnvelope[QuizAttemptResultRead],
    operation_id="student_submit_my_quiz",
    summary="Submit quiz answers (idempotent) and get immediate results (T-146)",
    dependencies=[require_role("student")],
)
async def submit_my_quiz(
    assignment_id: str,
    payload: QuizSubmitRequest,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    result = await QuizService(db).submit_my_quiz(claims, assignment_id, payload)
    return success(result.model_dump(mode="json"))


@teacher_router.get(
    "/{lecture_id}/quiz-results",
    response_model=SuccessEnvelope[list[TeacherStudentQuizResultRead]],
    operation_id="teacher_list_lecture_quiz_results",
    summary="Per-student quiz results for a lecture (T-147)",
    dependencies=[require_role("teacher")],
)
async def teacher_quiz_results(
    lecture_id: str,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    rows = await QuizService(db).teacher_results_for_lecture(claims, lecture_id)
    return success([r.model_dump(mode="json") for r in rows])


@teacher_router.get(
    "/{lecture_id}/quiz-aggregate",
    response_model=SuccessEnvelope[QuizOfferingAggregateRead],
    operation_id="teacher_get_lecture_quiz_aggregate",
    summary="Class aggregate quiz results for a lecture (T-147)",
    dependencies=[require_role("teacher")],
)
async def teacher_quiz_aggregate(
    lecture_id: str,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    result = await QuizService(db).teacher_aggregate_for_lecture(claims, lecture_id)
    return success(result.model_dump(mode="json"))
