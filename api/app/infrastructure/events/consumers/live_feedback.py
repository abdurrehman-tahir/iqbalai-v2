"""Live Feedback Consumer — aggregates session metrics → WebSocket (T-177)."""

from __future__ import annotations

import asyncio
import time
from typing import Any

import structlog

from app.config import get_settings
from app.features.live_feedback.metrics import compute_live_feedback_metrics
from app.infrastructure.events.consumer import consume
from app.infrastructure.events.subjects import (
    LIVE_FEEDBACK_CONSUMER,
    STUDENT_LECTURE_SESSION_CLOSED,
    STUDENT_LECTURE_WILDCARD,
)
from app.infrastructure.realtime import pubsub as realtime_pubsub

logger = structlog.get_logger(__name__)

# Active sessions keyed by user_id → session metadata for the 60s ticker.
_ACTIVE_SESSIONS: dict[str, dict[str, Any]] = {}
_TICKER_TASK: asyncio.Task[None] | None = None


def live_feedback_channel(user_id: str) -> str:
    """WebSocket/Redis channel ``student.live_feedback.{user_id}`` (Flow 6 §3.7)."""
    return f"student.live_feedback.{user_id}"


def redis_ws_channel(user_id: str) -> str:
    """Redis pub/sub channel for multi-container fan-out (ARCH §9.12)."""
    return f"ws:live_feedback:{user_id}"


def reset_active_sessions() -> None:
    """Test helper."""
    _ACTIVE_SESSIONS.clear()


def get_active_session(user_id: str) -> dict[str, Any] | None:
    return _ACTIVE_SESSIONS.get(user_id)


async def handle_live_feedback_event(envelope: dict[str, Any]) -> None:
    """Track active sessions from lecture events (push cadence is the ticker)."""
    event_type = str(envelope.get("event_type") or "")
    user_id = str(envelope.get("user_id") or "")
    if not user_id:
        return

    payload = envelope.get("payload") if isinstance(envelope.get("payload"), dict) else {}
    session_id = str(envelope.get("session_id") or payload.get("session_id") or "")
    lecture_id = str(envelope.get("lecture_id") or payload.get("lecture_id") or "")
    tenant_type = str(envelope.get("tenant_type") or "school")
    tenant_id = str(envelope.get("tenant_id") or "")

    if event_type in {STUDENT_LECTURE_SESSION_CLOSED, "student.lecture.session_closed"}:
        current = _ACTIVE_SESSIONS.get(user_id)
        if current and (not session_id or current.get("session_id") == session_id):
            _ACTIVE_SESSIONS.pop(user_id, None)
            logger.info("live_feedback_session_closed", user_id=user_id, session_id=session_id)
        return

    if not session_id:
        return

    entry = _ACTIVE_SESSIONS.get(user_id) or {
        "session_id": session_id,
        "lecture_id": lecture_id,
        "tenant_type": tenant_type,
        "tenant_id": tenant_id,
        "opened_at": time.time(),
        "question_count": 0,
        "last_page_id": None,
        "page_entered_at": time.time(),
        "questions_before_nudge": 0,
        "nudge_fired": False,
    }
    entry["session_id"] = session_id
    entry["lecture_id"] = lecture_id or entry.get("lecture_id")
    entry["tenant_type"] = tenant_type
    entry["tenant_id"] = tenant_id
    entry["last_event_at"] = time.time()

    if event_type in {
        "student.lecture.question_asked",
        "student.question.asked",
    }:
        entry["question_count"] = int(entry.get("question_count") or 0) + 1
        entry["questions_before_nudge"] = int(entry.get("question_count") or 0)

    if event_type in {
        "student.lecture.page_change",
        "student.lecture.scroll",
    }:
        page_id = payload.get("page_id") or payload.get("paragraph_id")
        if page_id and page_id != entry.get("last_page_id"):
            entry["last_page_id"] = page_id
            entry["page_entered_at"] = time.time()

    if event_type in {"student.lecture.mode_switch", "student.lecture.mode_changed"}:
        entry["mode"] = payload.get("mode") or payload.get("active_mode")

    _ACTIVE_SESSIONS[user_id] = entry


async def push_feedback_tick(user_id: str, session_meta: dict[str, Any]) -> dict[str, Any]:
    """Compute metrics and publish one live-feedback tick."""
    metrics = await compute_live_feedback_metrics(
        user_id=user_id,
        session_id=str(session_meta.get("session_id") or ""),
        lecture_id=str(session_meta.get("lecture_id") or ""),
        tenant_type=str(session_meta.get("tenant_type") or "school"),
        opened_at=float(session_meta.get("opened_at") or time.time()),
        question_count=int(session_meta.get("question_count") or 0),
        page_entered_at=float(session_meta.get("page_entered_at") or time.time()),
        last_page_id=session_meta.get("last_page_id"),
        nudge_fired=bool(session_meta.get("nudge_fired")),
    )
    stuck = metrics.get("stuck_nudge")
    if isinstance(stuck, dict) and stuck.get("should_show"):
        session_meta["nudge_fired"] = True
        metrics["stuck_nudge"] = {**stuck, "already_fired": True, "should_show": True}
    message = {
        "type": "live_feedback_update",
        "channel": live_feedback_channel(user_id),
        "user_id": user_id,
        "session_id": session_meta.get("session_id"),
        "payload": metrics,
    }
    await realtime_pubsub.publish(redis_ws_channel(user_id), message)
    logger.debug("live_feedback_tick_pushed", user_id=user_id)
    return message


async def _ticker_loop() -> None:
    settings = get_settings()
    interval = max(1, int(settings.LIVE_FEEDBACK_TICK_SECONDS))
    while True:
        await asyncio.sleep(interval)
        for user_id, meta in list(_ACTIVE_SESSIONS.items()):
            try:
                await push_feedback_tick(user_id, meta)
                # Persist nudge_fired back if metrics set it.
                stuck = (meta.get("_last_metrics") or {}).get("stuck_nudge")
                if isinstance(stuck, dict) and stuck.get("should_show"):
                    meta["nudge_fired"] = True
            except Exception as exc:
                logger.warning(
                    "live_feedback_tick_failed",
                    user_id=user_id,
                    error=str(exc),
                )


def ensure_ticker_started() -> None:
    global _TICKER_TASK
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    if _TICKER_TASK is None or _TICKER_TASK.done():
        _TICKER_TASK = loop.create_task(_ticker_loop(), name="m14-live-feedback-ticker")


async def run_live_feedback_consumer() -> None:
    ensure_ticker_started()
    await consume(
        STUDENT_LECTURE_WILDCARD,
        handle_live_feedback_event,
        durable_name=LIVE_FEEDBACK_CONSUMER,
    )
