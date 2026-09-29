"""Best-effort NATS publish for lecture lifecycle — T-116 / T-142 / T-163 / T-173.

Student study-session subjects follow ARCH §9 + flow-6 §3.8
(``student.lecture.{event_type}``). T-173 bridges M-12 ticket subjects onto
ARCH ``student.lecture.*`` subjects via ``M12_TO_ARCH_ALIAS``.
"""

from __future__ import annotations

from typing import Any

import structlog

from app.infrastructure.events.publisher import publish
from app.infrastructure.events.subjects import (
    M12_TO_ARCH_ALIAS,
    STUDENT_LECTURE_HIGHLIGHT_CREATED,
    STUDENT_LECTURE_MODE_SWITCH,
    STUDENT_LECTURE_PAGE_CHANGE,
    STUDENT_LECTURE_QUESTION_ASKED,
    STUDENT_LECTURE_SCROLL,
    STUDENT_LECTURE_SESSION_CLOSED,
    STUDENT_LECTURE_SESSION_OPENED,
)

logger = structlog.get_logger(__name__)

LECTURE_GENERATION_REQUESTED = "lecture.generation_requested"
LECTURE_VERSION_CREATED = "lecture.version.created"
LECTURE_GENERATION_FAILED = "lecture.generation_failed"
LECTURE_GENERATION_TIMED_OUT = "lecture.generation_timed_out"
LECTURE_PUBLISHED = "lecture.published"

# Re-export ARCH subject constants for lecture_session / tests.
__all__ = [
    "LECTURE_GENERATION_REQUESTED",
    "LECTURE_VERSION_CREATED",
    "LECTURE_GENERATION_FAILED",
    "LECTURE_GENERATION_TIMED_OUT",
    "LECTURE_PUBLISHED",
    "STUDENT_LECTURE_SESSION_OPENED",
    "STUDENT_LECTURE_SESSION_CLOSED",
    "STUDENT_LECTURE_QUESTION_ASKED",
    "STUDENT_LECTURE_HIGHLIGHT_CREATED",
    "STUDENT_LECTURE_SCROLL",
    "STUDENT_LECTURE_PAGE_CHANGE",
    "STUDENT_LECTURE_MODE_SWITCH",
    "publish_lecture_event",
    "publish_student_lecture_event",
    "publish_session_opened",
    "publish_session_closed",
    "publish_question_asked",
    "publish_highlight_created",
    "publish_scroll",
    "publish_page_change",
    "publish_mode_switch",
]


async def publish_lecture_event(*, event_type: str, payload: dict[str, Any]) -> None:
    """Publish after commit; never raises into the caller path."""
    try:
        await publish(
            event_type,
            event_type,
            payload,
            tenant_id=str(payload.get("school_id", "")),
            tenant_type=str(payload.get("tenant_type", "school")),
            user_id=str(payload.get("teacher_user_id", "")),
            lecture_id=str(payload.get("lecture_id") or ""),
        )
    except Exception as exc:
        logger.warning("lecture_event_publish_failed", event_type=event_type, error=str(exc))


async def publish_student_lecture_event(
    *,
    event_type: str,
    payload: dict[str, Any],
) -> None:
    """Tenant-tagged student event publish; best-effort after commit.

    When ``event_type`` is an M-12 ticket subject, also publishes the ARCH
    ``student.lecture.*`` alias so M-14 consumers receive the locked taxonomy.
    """
    try:
        kwargs = dict(
            tenant_id=str(payload.get("school_id") or ""),
            tenant_type=str(payload.get("tenant_type") or "school"),
            user_id=str(payload.get("student_user_id") or ""),
            session_id=str(payload.get("session_id") or ""),
            lecture_id=str(payload.get("lecture_id") or ""),
        )
        await publish(event_type, event_type, payload, **kwargs)
        alias = M12_TO_ARCH_ALIAS.get(event_type)
        if alias and alias != event_type:
            await publish(alias, alias, payload, **kwargs)
    except Exception as exc:
        logger.warning(
            "student_lecture_event_publish_failed",
            event_type=event_type,
            error=str(exc),
        )


async def publish_session_opened(*, payload: dict[str, Any]) -> None:
    await publish_student_lecture_event(
        event_type=STUDENT_LECTURE_SESSION_OPENED,
        payload=payload,
    )


async def publish_session_closed(*, payload: dict[str, Any]) -> None:
    await publish_student_lecture_event(
        event_type=STUDENT_LECTURE_SESSION_CLOSED,
        payload=payload,
    )


async def publish_question_asked(*, payload: dict[str, Any]) -> None:
    await publish_student_lecture_event(
        event_type=STUDENT_LECTURE_QUESTION_ASKED,
        payload=payload,
    )


async def publish_highlight_created(*, payload: dict[str, Any]) -> None:
    await publish_student_lecture_event(
        event_type=STUDENT_LECTURE_HIGHLIGHT_CREATED,
        payload=payload,
    )


async def publish_scroll(*, payload: dict[str, Any]) -> None:
    await publish_student_lecture_event(event_type=STUDENT_LECTURE_SCROLL, payload=payload)


async def publish_page_change(*, payload: dict[str, Any]) -> None:
    await publish_student_lecture_event(
        event_type=STUDENT_LECTURE_PAGE_CHANGE,
        payload=payload,
    )


async def publish_mode_switch(*, payload: dict[str, Any]) -> None:
    await publish_student_lecture_event(
        event_type=STUDENT_LECTURE_MODE_SWITCH,
        payload=payload,
    )
