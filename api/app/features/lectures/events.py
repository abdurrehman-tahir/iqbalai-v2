"""Best-effort NATS publish for lecture lifecycle — T-116 / T-142 / T-163.

Student study-session subjects follow ARCH §9 + flow-6 §3.8
(``student.lecture.{event_type}``). T-163 narrative aliases
``lecture.session.opened`` / ``lecture.session.ended`` map to
``session_opened`` / ``session_closed`` below.

BLOCKED-HOOK: Cognitive DNA interaction-signal consumer (session/question
events → DNA update) → Flow 9 / M-18 (events emitted here; consumer built
when Flow 9 ships). Emit-only in M-12 — M-14 owns the JetStream consumers.
"""

from __future__ import annotations

from typing import Any

import structlog

from app.infrastructure.events.publisher import publish

logger = structlog.get_logger(__name__)

LECTURE_GENERATION_REQUESTED = "lecture.generation_requested"
LECTURE_VERSION_CREATED = "lecture.version.created"
# T-126: generation success is already covered by LECTURE_VERSION_CREATED above
# (M-09 has no auto-quiz gate, so version-created == generation-complete); these
# two cover the failure paths, which previously had no NATS event at all.
LECTURE_GENERATION_FAILED = "lecture.generation_failed"
LECTURE_GENERATION_TIMED_OUT = "lecture.generation_timed_out"
# T-142 — lecture publish lifecycle (Flow 5 §3.5)
LECTURE_PUBLISHED = "lecture.published"

# T-163 — student lecture study session (ARCH §9 / flow-6 §3.8)
STUDENT_LECTURE_SESSION_OPENED = "student.lecture.session_opened"
STUDENT_LECTURE_SESSION_CLOSED = "student.lecture.session_closed"


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
        )
    except Exception as exc:
        logger.warning("lecture_event_publish_failed", event_type=event_type, error=str(exc))


async def publish_student_lecture_event(
    *,
    event_type: str,
    payload: dict[str, Any],
) -> None:
    """Tenant-tagged student.lecture.* publish; best-effort after commit."""
    try:
        await publish(
            event_type,
            event_type,
            payload,
            tenant_id=str(payload.get("school_id") or ""),
            tenant_type=str(payload.get("tenant_type") or "school"),
            user_id=str(payload.get("student_user_id") or ""),
            session_id=str(payload.get("session_id") or ""),
        )
    except Exception as exc:
        logger.warning(
            "student_lecture_event_publish_failed",
            event_type=event_type,
            error=str(exc),
        )


async def publish_session_opened(*, payload: dict[str, Any]) -> None:
    """Emit ``student.lecture.session_opened`` (T-163 / ARCH §9)."""
    await publish_student_lecture_event(
        event_type=STUDENT_LECTURE_SESSION_OPENED,
        payload=payload,
    )


async def publish_session_closed(*, payload: dict[str, Any]) -> None:
    """Emit ``student.lecture.session_closed`` with session summary (T-163).

    Ticket narrative name is ``lecture.session.ended``; subject follows ARCH.
    """
    await publish_student_lecture_event(
        event_type=STUDENT_LECTURE_SESSION_CLOSED,
        payload=payload,
    )
