"""Best-effort NATS publish when a diagnostic completes (T-106).

Subject: ``student.diagnostic_completed`` (ticket acceptance + ``student.>`` stream).
ARCH §9.3 also lists ``diagnostic.completed`` — prefer the ticket/stream-aligned
name until an amendment reconciles the taxonomy.
"""

from __future__ import annotations

from typing import Any, Literal

import structlog

logger = structlog.get_logger(__name__)

DIAGNOSTIC_COMPLETED_SUBJECT = "student.diagnostic_completed"


async def publish_diagnostic_completed(
    *,
    diagnostic_id: str,
    student_user_id: str,
    tenant_type: Literal["school", "independent"],
    subject_id: str | None,
    framework_id: str | None,
    completed_at: str | None,
    timed_out: bool,
    tenant_id: str = "",
) -> None:
    """Publish after DNA + diagnostic commits (ARCH §9.9). Best-effort."""
    payload: dict[str, Any] = {
        "diagnostic_id": diagnostic_id,
        "student_user_id": student_user_id,
        "subject_id": subject_id,
        "framework_id": framework_id,
        "tenant_type": tenant_type,
        "completed_at": completed_at,
        "timed_out": timed_out,
    }
    try:
        from app.infrastructure.events.publisher import publish

        await publish(
            subject=DIAGNOSTIC_COMPLETED_SUBJECT,
            event_type=DIAGNOSTIC_COMPLETED_SUBJECT,
            payload=payload,
            tenant_id=tenant_id or student_user_id,
            tenant_type=tenant_type,
            user_id=student_user_id,
        )
    except Exception as exc:
        logger.warning(
            "diagnostic_completed_event_publish_skipped",
            diagnostic_id=diagnostic_id,
            error=str(exc),
        )
