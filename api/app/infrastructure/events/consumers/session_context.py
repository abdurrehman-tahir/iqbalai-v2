"""AI Session Context Consumer — question_asked → session_difficulty_log (T-176)."""

from __future__ import annotations

from typing import Any

import structlog

from app.db.session import async_session_factory
from app.features.session_difficulty.repository import increment_question_count
from app.features.session_difficulty.subtopic import resolve_sub_topic_id
from app.infrastructure.events.consumer import consume
from app.infrastructure.events.subjects import (
    SESSION_CONTEXT_CONSUMER,
    STUDENT_LECTURE_QUESTION_ASKED,
)

logger = structlog.get_logger(__name__)


async def handle_session_context_event(envelope: dict[str, Any]) -> None:
    """Increment difficulty log for the question's sub-topic."""
    event_type = str(envelope.get("event_type") or "")
    if event_type not in {
        STUDENT_LECTURE_QUESTION_ASKED,
        "student.question.asked",
    }:
        return

    raw_payload = envelope.get("payload")
    payload: dict[str, Any] = raw_payload if isinstance(raw_payload, dict) else {}
    session_id = str(envelope.get("session_id") or payload.get("session_id") or "")
    if not session_id:
        logger.warning("session_context_missing_session_id", event_type=event_type)
        return

    source_chunk_id = payload.get("source_chunk_id")
    lecture_id = str(envelope.get("lecture_id") or payload.get("lecture_id") or "") or None
    paragraph_id = str(payload.get("paragraph_id")) if payload.get("paragraph_id") else None
    tenant_type = str(envelope.get("tenant_type") or "school")

    async with async_session_factory() as session:
        sub_topic_id = await resolve_sub_topic_id(
            session,
            source_chunk_id=str(source_chunk_id) if source_chunk_id else None,
            lecture_id=lecture_id,
            paragraph_id=paragraph_id,
        )
        if not sub_topic_id:
            logger.info(
                "session_context_no_subtopic",
                session_id=session_id,
                event_type=event_type,
            )
            return
        row = await increment_question_count(
            session,
            session_id=session_id,
            sub_topic_id=sub_topic_id,
            tenant_type=tenant_type,
        )
        await session.commit()
    logger.info(
        "session_difficulty_incremented",
        session_id=session_id,
        sub_topic_id=sub_topic_id,
        question_count=row.question_count,
        tenant_type=tenant_type,
    )


async def run_session_context_consumer() -> None:
    await consume(
        STUDENT_LECTURE_QUESTION_ASKED,
        handle_session_context_event,
        durable_name=SESSION_CONTEXT_CONSUMER,
    )
