"""Quiz feature NATS event helpers (T-146 / T-148)."""

from __future__ import annotations

from typing import Any

from app.infrastructure.events.publisher import publish

STUDENT_QUIZ_COMPLETED = "student.quiz.completed"
STUDENT_ENROLLED = "student.enrolled"


async def publish_student_quiz_completed(*, payload: dict[str, Any]) -> None:
    await publish(
        STUDENT_QUIZ_COMPLETED,
        STUDENT_QUIZ_COMPLETED,
        payload,
        tenant_id=str(payload.get("school_id") or ""),
        tenant_type="school",
        user_id=str(payload.get("student_user_id") or ""),
    )


async def publish_student_enrolled(*, payload: dict[str, Any]) -> None:
    await publish(
        STUDENT_ENROLLED,
        STUDENT_ENROLLED,
        payload,
        tenant_id=str(payload.get("school_id") or ""),
        tenant_type="school",
        user_id=str(payload.get("student_user_id") or ""),
    )
