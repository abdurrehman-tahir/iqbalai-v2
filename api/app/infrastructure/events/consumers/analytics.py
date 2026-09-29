"""Analytics Consumer — durable ``student.lecture.*`` → student_events (T-174)."""

from __future__ import annotations

from typing import Any

import structlog

from app.db.session import async_session_factory
from app.features.student_events.repository import persist_student_event
from app.infrastructure.events.consumer import consume
from app.infrastructure.events.subjects import (
    ANALYTICS_CONSUMER,
    STUDENT_LECTURE_WILDCARD,
)

logger = structlog.get_logger(__name__)


async def handle_analytics_event(envelope: dict[str, Any]) -> None:
    """Persist one envelope; tenant routing is inside the repository."""
    async with async_session_factory() as session:
        row_id = await persist_student_event(session, envelope)
        await session.commit()
    logger.info(
        "analytics_event_persisted",
        event_type=envelope.get("event_type"),
        tenant_type=envelope.get("tenant_type"),
        row_id=row_id,
    )


async def run_analytics_consumer() -> None:
    """Blocking durable subscription (independent of other consumers)."""
    await consume(
        STUDENT_LECTURE_WILDCARD,
        handle_analytics_event,
        durable_name=ANALYTICS_CONSUMER,
    )
