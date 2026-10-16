"""NATS publish helpers for self-study sessions + goals — T-210 / T-211."""

from __future__ import annotations

from typing import Any

import structlog

from app.features.lectures.events import publish_student_lecture_event
from app.features.self_study.sessions import event_reaches_flow7
from app.infrastructure.events.publisher import publish

logger = structlog.get_logger(__name__)

SELF_STUDY_SESSION_STARTED = "student.study_session.started"
SELF_STUDY_SESSION_ENDED = "student.study_session.ended"
SELF_STUDY_GOAL_SET = "self_study.goal_set"
SELF_STUDY_GOAL_ACHIEVED = "self_study.goal_achieved"
SELF_STUDY_MATERIAL_UPLOADED = "self_study.material_uploaded"
SELF_STUDY_PLAN_GENERATED = "self_study.plan_generated"
SELF_STUDY_ADHERENCE_UPDATED = "self_study.adherence_updated"
SELF_STUDY_ADHERENCE_ALERT = "self_study.adherence_alert"


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


async def _publish_self_study_subject(*, subject: str, payload: dict[str, Any]) -> None:
    tagged = tag_self_study_payload(payload)
    try:
        await publish(
            subject,
            subject,
            tagged,
            tenant_id=str(tagged.get("school_id") or ""),
            tenant_type=str(tagged.get("tenant_type") or "school"),
            user_id=str(tagged.get("student_user_id") or ""),
            session_id=str(tagged.get("session_id") or ""),
        )
    except Exception as exc:
        logger.warning(
            "self_study_event_publish_failed",
            subject=subject,
            error=str(exc),
        )


async def publish_self_study_goal_set(*, payload: dict[str, Any]) -> None:
    """A-005 — emit after commit (ARCH §9.9)."""
    await _publish_self_study_subject(subject=SELF_STUDY_GOAL_SET, payload=payload)


async def publish_self_study_goal_achieved(*, payload: dict[str, Any]) -> None:
    await _publish_self_study_subject(subject=SELF_STUDY_GOAL_ACHIEVED, payload=payload)


async def publish_self_study_material_uploaded(*, payload: dict[str, Any]) -> None:
    """A-006 — Instant Answer and Add-to-Library both emit (ARCH §9.9)."""
    await _publish_self_study_subject(subject=SELF_STUDY_MATERIAL_UPLOADED, payload=payload)


async def publish_self_study_plan_generated(*, payload: dict[str, Any]) -> None:
    await _publish_self_study_subject(subject=SELF_STUDY_PLAN_GENERATED, payload=payload)


async def publish_self_study_adherence_updated(*, payload: dict[str, Any]) -> None:
    """A-007 — Flow 9 consumes adherence % (not computed here)."""
    await _publish_self_study_subject(subject=SELF_STUDY_ADHERENCE_UPDATED, payload=payload)


async def publish_self_study_adherence_alert(*, payload: dict[str, Any]) -> None:
    await _publish_self_study_subject(subject=SELF_STUDY_ADHERENCE_ALERT, payload=payload)


def should_forward_to_flow7(payload: dict[str, Any]) -> bool:
    """Gate used by overnight review consumers (independent never forwards)."""
    return event_reaches_flow7(
        tenant_type=str(payload.get("tenant_type") or "school"),
        mode=str(payload.get("mode") or ""),
        teacher_activity_share=str(payload.get("teacher_activity_share") or "share"),
    )
