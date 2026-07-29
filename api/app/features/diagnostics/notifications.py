"""Diagnostic lifecycle notifications — T-109 (self_study namespace).

NATS for completed is already emitted in ``events.publish_diagnostic_completed``.
Mode transitions publish via ``student_mode.events`` (T-101). This module only
fires in-app templates.
"""

from __future__ import annotations

from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.diagnostics.schemas import FocusAreaRead

logger = structlog.get_logger(__name__)


def format_focus_areas_param(areas: list[FocusAreaRead], *, limit: int = 5) -> str:
    """Comma-separated topics for notification body — never grades/scores."""
    topics = [a.topic.strip() for a in areas if a.topic.strip()][:limit]
    if not topics:
        return "your next study topics"
    return ", ".join(topics)


async def notify_diagnostic_available(
    *,
    session: AsyncSession,
    recipient_user_id: str,
    school_id: str | None,
    locale: str,
) -> None:
    from app.infrastructure.notifications.self_study import notify_self_study_event

    await notify_self_study_event(
        session=session,
        template_key="self_study.diagnostic_available",
        recipient_user_id=recipient_user_id,
        school_id=school_id,
        locale=locale,
        metadata={"event": "diagnostic_available"},
    )


async def notify_diagnostic_completed(
    *,
    session: AsyncSession,
    recipient_user_id: str,
    school_id: str | None,
    locale: str,
    focus_areas: list[FocusAreaRead],
    diagnostic_id: str,
) -> None:
    from app.infrastructure.notifications.self_study import notify_self_study_event

    summary = format_focus_areas_param(focus_areas)
    await notify_self_study_event(
        session=session,
        template_key="self_study.diagnostic_completed",
        recipient_user_id=recipient_user_id,
        school_id=school_id,
        locale=locale,
        params={"focus_areas": summary},
        metadata={
            "event": "diagnostic_completed",
            "diagnostic_id": diagnostic_id,
            "focus_areas": summary,
        },
    )


async def notify_diagnostic_retake_available(
    *,
    session: AsyncSession,
    recipient_user_id: str,
    school_id: str | None,
    locale: str,
    diagnostic_id: str,
) -> None:
    from app.infrastructure.notifications.self_study import notify_self_study_event

    await notify_self_study_event(
        session=session,
        template_key="self_study.diagnostic_retake_available",
        recipient_user_id=recipient_user_id,
        school_id=school_id,
        locale=locale,
        metadata={"event": "diagnostic_retake_available", "diagnostic_id": diagnostic_id},
    )


async def safe_notify(coro: Any) -> None:
    """Best-effort wrapper so notification failures never roll back lifecycle."""
    try:
        await coro
    except Exception as exc:
        logger.warning("diagnostic_notification_skipped", error=str(exc))
