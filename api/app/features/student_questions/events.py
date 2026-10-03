"""NATS helpers for student lecture questions + highlights (T-156 / T-163 / T-173).

Publishes M-12 ticket subjects; ``publish_student_lecture_event`` dual-publishes
the ARCH ``student.lecture.*`` aliases for M-14 consumers.
"""

from __future__ import annotations

from typing import Any

from app.features.lectures.events import publish_student_lecture_event

STUDENT_QUESTION_ASKED = "student.question.asked"
STUDENT_HIGHLIGHT_CREATED = "student.highlight.created"


async def publish_student_question_asked(*, payload: dict[str, Any]) -> None:
    """Emit ``student.question.asked`` (+ ARCH alias via dual-publish)."""
    await publish_student_lecture_event(event_type=STUDENT_QUESTION_ASKED, payload=payload)


async def publish_student_highlight_created(*, payload: dict[str, Any]) -> None:
    """Emit ``student.highlight.created`` (+ ARCH alias via dual-publish)."""
    await publish_student_lecture_event(event_type=STUDENT_HIGHLIGHT_CREATED, payload=payload)
