"""NATS publish helpers for self-study sessions — T-210."""

from __future__ import annotations

from typing import Any

from app.features.lectures.events import publish_student_lecture_event
from app.features.self_study.sessions import event_reaches_flow7

SELF_STUDY_SESSION_STARTED = "student.study_session.started"
SELF_STUDY_SESSION_ENDED = "student.study_session.ended"


def tag_self_study_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Ensure every self-study interaction event carries mode + tenant_type."""
    out = dict(payload)
    out.setdefault("mode", "self_study")
    if "tenant_type" not in out:
        out["tenant_type"] = "school"
    return out


async def publish_self_study_session_started(*, payload: dict[str, Any]) -> None:
    tagged = tag_self_study_payload(payload)
    await publish_student_lecture_event(
        event_type=SELF_STUDY_SESSION_STARTED,
        payload=tagged,
    )


async def publish_self_study_session_ended(*, payload: dict[str, Any]) -> None:
    tagged = tag_self_study_payload(payload)
    await publish_student_lecture_event(
        event_type=SELF_STUDY_SESSION_ENDED,
        payload=tagged,
    )


def should_forward_to_flow7(payload: dict[str, Any]) -> bool:
    """Gate used by overnight review consumers (independent never forwards)."""
    return event_reaches_flow7(
        tenant_type=str(payload.get("tenant_type") or "school"),
        mode=str(payload.get("mode") or ""),
        teacher_activity_share=str(payload.get("teacher_activity_share") or "share"),
    )
