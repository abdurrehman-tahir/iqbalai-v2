"""Student lecture interaction events REST — scroll / page_change / mode_switch (T-173)."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db, require_role
from app.core.responses import SuccessEnvelope, success
from app.features.lectures.events import (
    publish_mode_switch,
    publish_page_change,
    publish_scroll,
)
from app.features.lectures.lecture_session import LectureSessionService

router = APIRouter(prefix="/students/me/lectures", tags=["student-lecture-events"])

EventKind = Literal["scroll", "page_change", "mode_switch"]


class LectureInteractionEventIn(BaseModel):
    event_type: EventKind
    lecture_id: str | None = Field(default=None, max_length=36)
    page_id: str | None = Field(default=None, max_length=128)
    paragraph_id: str | None = Field(default=None, max_length=36)
    mode: str | None = Field(default=None, max_length=32)
    scroll_y: float | None = None


class LectureInteractionEventOut(BaseModel):
    accepted: bool
    event_type: str


@router.post(
    "/sessions/{session_id}/events",
    response_model=SuccessEnvelope[LectureInteractionEventOut],
    operation_id="post_student_lecture_interaction_event",
    summary="Emit student.lecture scroll/page_change/mode_switch (T-173)",
    dependencies=[require_role("student")],
)
async def post_interaction_event(
    session_id: str,
    body: LectureInteractionEventIn,
    claims: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessEnvelope[LectureInteractionEventOut]:
    """Accept interaction events and publish to NATS (owner session only)."""
    svc = LectureSessionService(db)
    session = await svc.get_session(claims, session_id)
    payload = {
        "session_id": session_id,
        "lecture_id": body.lecture_id or session.lecture_id,
        "student_user_id": str(claims.get("sub") or ""),
        "school_id": str(claims.get("school_id") or ""),
        "tenant_type": str(claims.get("tenant_type") or "school"),
        "page_id": body.page_id,
        "paragraph_id": body.paragraph_id,
        "mode": body.mode,
        "scroll_y": body.scroll_y,
    }
    if body.event_type == "scroll":
        await publish_scroll(payload=payload)
    elif body.event_type == "page_change":
        await publish_page_change(payload=payload)
    else:
        await publish_mode_switch(payload=payload)
    return success(LectureInteractionEventOut(accepted=True, event_type=body.event_type))
