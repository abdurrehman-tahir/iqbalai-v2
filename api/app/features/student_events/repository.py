"""Persist NATS envelopes into tenant-routed student_events (T-174)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.features.student_events.models import (
    IndependentStudentEvent,
    SchoolStudentEvent,
    StudentEventTenantType,
)


def _parse_occurred_at(envelope: dict[str, Any]) -> datetime:
    raw = envelope.get("timestamp") or envelope.get("occurred_at")
    if isinstance(raw, str) and raw:
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            pass
    return datetime.now(timezone.utc)


def _tenant_type(envelope: dict[str, Any]) -> StudentEventTenantType:
    raw = str(envelope.get("tenant_type") or "school").lower()
    if raw == StudentEventTenantType.INDEPENDENT.value:
        return StudentEventTenantType.INDEPENDENT
    return StudentEventTenantType.SCHOOL


async def persist_student_event(session: AsyncSession, envelope: dict[str, Any]) -> str:
    """Insert one event into the correct schema store; return row id.

    School and independent stores never cross — routing is exclusively by
    envelope ``tenant_type``.
    """
    tenant_type = _tenant_type(envelope)
    payload = envelope.get("payload")
    if not isinstance(payload, dict):
        payload = {}
    lecture_id = str(envelope.get("lecture_id") or payload.get("lecture_id") or "") or None
    session_id = str(envelope.get("session_id") or payload.get("session_id") or "") or None
    tenant_id = str(envelope.get("tenant_id") or "") or None
    user_id = str(envelope.get("user_id") or payload.get("student_user_id") or "")
    event_type = str(envelope.get("event_type") or "")
    occurred_at = _parse_occurred_at(envelope)

    if tenant_type is StudentEventTenantType.INDEPENDENT:
        row: SchoolStudentEvent | IndependentStudentEvent = IndependentStudentEvent(
            tenant_type=StudentEventTenantType.INDEPENDENT,
            tenant_id=tenant_id,
            user_id=user_id,
            session_id=session_id,
            lecture_id=lecture_id,
            event_type=event_type,
            event_payload_jsonb=dict(payload),
            occurred_at=occurred_at,
        )
    else:
        row = SchoolStudentEvent(
            tenant_type=StudentEventTenantType.SCHOOL,
            tenant_id=tenant_id,
            user_id=user_id,
            session_id=session_id,
            lecture_id=lecture_id,
            event_type=event_type,
            event_payload_jsonb=dict(payload),
            occurred_at=occurred_at,
        )
    session.add(row)
    await session.flush()
    return str(row.id)
