"""NATS helpers for student lecture questions + highlights (T-156 / T-163).

Subjects:
- ``student.question.asked`` — every question submit (T-156)
- ``student.highlight.created`` — when submit carries ``highlight_text`` (T-163)

ARCH §9 also lists ``student.lecture.question_asked`` /
``student.lecture.highlight_created``; M-12 keeps the T-156 / T-163 ticket
subjects that parallel existing ``student.<entity>.<event>`` conventions
(``student.quiz.completed``, etc.). M-14 stream wiring can bridge aliases.

BLOCKED-HOOK: Cognitive DNA interaction-signal consumer (session/question
events → DNA update) → Flow 9 / M-18 (events emitted here; consumer built
when Flow 9 ships). Emit-only — no consumers in M-12.
"""

from __future__ import annotations

from typing import Any

import structlog

from app.infrastructure.events.publisher import publish

logger = structlog.get_logger(__name__)

STUDENT_QUESTION_ASKED = "student.question.asked"
STUDENT_HIGHLIGHT_CREATED = "student.highlight.created"


async def _publish_student_event(*, event_type: str, payload: dict[str, Any]) -> None:
    """Best-effort emit after commit; never raises into the caller path."""
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
            "student_question_event_publish_failed",
            event_type=event_type,
            error=str(exc),
        )


async def publish_student_question_asked(*, payload: dict[str, Any]) -> None:
    """Emit ``student.question.asked`` (T-156; tenant-tagged in T-163)."""
    await _publish_student_event(event_type=STUDENT_QUESTION_ASKED, payload=payload)


async def publish_student_highlight_created(*, payload: dict[str, Any]) -> None:
    """Emit ``student.highlight.created`` when a question includes highlight text."""
    await _publish_student_event(event_type=STUDENT_HIGHLIGHT_CREATED, payload=payload)
