"""Student highlights + flashcards HTTP API — T-185 / T-188."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db, require_role
from app.core.responses import (
    DeletedResponse,
    PaginatedEnvelope,
    SuccessEnvelope,
    paginated,
    success,
)
from app.features.student_highlights.my_highlights import MAX_PAGE_SIZE, MyHighlightsService
from app.features.student_highlights.schemas import (
    FlashcardBackUpdate,
    LectureHighlightAggregateRead,
    MyHighlightRead,
    PairedFlashcardRead,
    StudentHighlightRead,
)
from app.features.student_highlights.service import StudentHighlightService

router = APIRouter(prefix="/students/me", tags=["student-highlights"])
parent_router = APIRouter(prefix="/parents/me", tags=["parent-student-highlights"])
staff_router = APIRouter(prefix="/school/lectures", tags=["school-highlight-aggregates"])


@router.get(
    "/lectures/{lecture_id}/highlights",
    response_model=SuccessEnvelope[list[StudentHighlightRead]],
    operation_id="student_list_lecture_highlights",
    summary="List own highlights on a lecture with current yellow-mark positions (T-185)",
    dependencies=[require_role("student")],
)
async def list_lecture_highlights(
    lecture_id: str,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    rows = await StudentHighlightService(db).list_for_lecture(claims, lecture_id)
    return success([r.model_dump(mode="json") for r in rows])


@router.get(
    "/highlights",
    response_model=PaginatedEnvelope[MyHighlightRead],
    operation_id="student_list_my_highlights",
    summary="My Highlights: own highlights + paired flashcards, newest first (T-188)",
    dependencies=[require_role("student")],
)
async def list_my_highlights(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=MAX_PAGE_SIZE),
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    items, total = await MyHighlightsService(db).list_mine(claims, page=page, page_size=page_size)
    return paginated([i.model_dump(mode="json") for i in items], total, page, page_size)


@router.patch(
    "/flashcards/{flashcard_id}",
    response_model=SuccessEnvelope[PairedFlashcardRead],
    operation_id="student_update_flashcard_back",
    summary="Edit an own flashcard's back (placeholder cards, flow-6 §5.5) (T-188)",
    dependencies=[require_role("student")],
)
async def update_flashcard_back(
    flashcard_id: str,
    payload: FlashcardBackUpdate,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    card = await MyHighlightsService(db).update_flashcard_back(
        claims, flashcard_id=flashcard_id, back_text=payload.back_text
    )
    return success(card.model_dump(mode="json"))


@router.delete(
    "/highlights/{highlight_id}",
    response_model=SuccessEnvelope[DeletedResponse],
    operation_id="student_delete_highlight",
    summary="Delete an own highlight; its flashcard is removed with it (flow-6 §5.5) (T-188)",
    dependencies=[require_role("student")],
)
async def delete_highlight(
    highlight_id: str,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    await MyHighlightsService(db).delete_highlight(claims, highlight_id=highlight_id)
    return success(DeletedResponse().model_dump())


@parent_router.get(
    "/students/{student_user_id}/highlights",
    response_model=PaginatedEnvelope[MyHighlightRead],
    operation_id="parent_list_student_highlights",
    summary="Read-only highlights + flashcards for a linked child (respects #72) (T-188)",
    dependencies=[require_role("parent")],
)
async def parent_list_student_highlights(
    student_user_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=MAX_PAGE_SIZE),
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    items, total = await MyHighlightsService(db).list_for_parent(
        claims, student_user_id=student_user_id, page=page, page_size=page_size
    )
    return paginated([i.model_dump(mode="json") for i in items], total, page, page_size)


@staff_router.get(
    "/{lecture_id}/highlight-aggregate",
    response_model=SuccessEnvelope[LectureHighlightAggregateRead],
    operation_id="school_lecture_highlight_aggregate",
    summary="Anonymous highlight/flashcard counts for a lecture (Coordinator+, §6.19) (T-188)",
    dependencies=[require_role("coordinator")],
)
async def lecture_highlight_aggregate(
    lecture_id: str,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    agg = await MyHighlightsService(db).lecture_aggregate(claims, lecture_id=lecture_id)
    return success(agg.model_dump(mode="json"))
