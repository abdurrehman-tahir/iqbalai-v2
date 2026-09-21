"""Student lecture Q&A HTTP API — T-156 / T-157 / T-158 / T-160."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db, require_role
from app.core.idempotency import IdempotencyContext, idempotency_key
from app.core.responses import SuccessEnvelope, success
from app.features.student_questions.schemas import (
    ConversationTurnRead,
    StudentQuestionAnswerRead,
    StudentQuestionCreateRequest,
    StudentQuestionFollowUpRequest,
    StudentQuestionRead,
)
from app.features.student_questions.service import StudentQuestionService
from app.infrastructure.llm.streaming import stream_response

router = APIRouter(
    prefix="/students/me/lectures",
    tags=["student-lecture-questions"],
)


@router.post(
    "/{lecture_id}/sessions/{session_id}/questions",
    response_model=SuccessEnvelope[StudentQuestionRead],
    operation_id="student_ask_lecture_question",
    summary="Submit a lecture question (idempotent; classified) (T-156/T-157)",
    status_code=201,
    dependencies=[require_role("student")],
)
async def ask_lecture_question(
    lecture_id: str,
    session_id: str,
    payload: StudentQuestionCreateRequest,
    claims: dict[str, object] = Depends(get_current_user),
    idem: IdempotencyContext | None = Depends(idempotency_key),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    if idem is not None:
        cached = await idem.cached_response()
        if cached is not None:
            return cached

    result = await StudentQuestionService(db).ask_question(
        claims,
        lecture_id=lecture_id,
        session_id=session_id,
        payload=payload,
    )
    response = success(result.model_dump(mode="json"))
    if idem is not None:
        await idem.store_response(response)
    return response


@router.get(
    "/{lecture_id}/questions",
    response_model=SuccessEnvelope[list[StudentQuestionRead]],
    operation_id="student_list_lecture_questions",
    summary="List the student's questions (+ conversations) for a lecture (T-160)",
    dependencies=[require_role("student")],
)
async def list_lecture_questions(
    lecture_id: str,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    rows = await StudentQuestionService(db).list_for_lecture(claims, lecture_id)
    return success([r.model_dump(mode="json") for r in rows])


@router.get(
    "/{lecture_id}/questions/{question_id}/conversations",
    response_model=SuccessEnvelope[list[ConversationTurnRead]],
    operation_id="student_list_question_conversations",
    summary="List conversation turns for one question (T-160)",
    dependencies=[require_role("student")],
)
async def list_question_conversations(
    lecture_id: str,
    question_id: str,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    rows = await StudentQuestionService(db).list_conversations(
        claims, lecture_id=lecture_id, question_id=question_id
    )
    return success([r.model_dump(mode="json") for r in rows])


@router.post(
    "/{lecture_id}/questions/{question_id}/turns",
    response_model=SuccessEnvelope[StudentQuestionRead],
    operation_id="student_follow_up_lecture_question",
    summary="Append a follow-up turn to a lecture question thread (T-160)",
    status_code=201,
    dependencies=[require_role("student")],
)
async def follow_up_lecture_question(
    lecture_id: str,
    question_id: str,
    payload: StudentQuestionFollowUpRequest,
    claims: dict[str, object] = Depends(get_current_user),
    idem: IdempotencyContext | None = Depends(idempotency_key),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    if idem is not None:
        cached = await idem.cached_response()
        if cached is not None:
            return cached

    result = await StudentQuestionService(db).add_follow_up(
        claims,
        lecture_id=lecture_id,
        question_id=question_id,
        payload=payload,
    )
    response = success(result.model_dump(mode="json"))
    if idem is not None:
        await idem.store_response(response)
    return response


@router.get(
    "/{lecture_id}/questions/{question_id}/answer",
    response_model=SuccessEnvelope[StudentQuestionAnswerRead],
    operation_id="student_get_lecture_question_answer",
    summary="Get the persisted AI answer + source badges for a question (T-158)",
    dependencies=[require_role("student")],
)
async def get_lecture_question_answer(
    lecture_id: str,
    question_id: str,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    result = await StudentQuestionService(db).get_answer(
        claims, lecture_id=lecture_id, question_id=question_id
    )
    return success(result.model_dump(mode="json"))


@router.get(
    "/{lecture_id}/questions/{question_id}/answer/stream",
    response_model=None,
    operation_id="student_stream_lecture_question_answer",
    summary="Stream the AI answer token-by-token (SSE; T-158)",
    dependencies=[require_role("student")],
)
async def stream_lecture_question_answer(
    lecture_id: str,
    question_id: str,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    # StreamingResponse cannot declare a JSON response_model; tokens are SSE text.
    # Final answer + source badges are persisted and available via GET .../answer.
    # Await access checks first so 403/404 are raised before headers are sent.
    generator = await StudentQuestionService(db).stream_answer(
        claims, lecture_id=lecture_id, question_id=question_id
    )
    return stream_response(generator)
