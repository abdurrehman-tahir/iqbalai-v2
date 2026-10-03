"""Live feedback metrics computation (T-179 / T-181 stuck nudge)."""

from __future__ import annotations

import time
from typing import Any

from app.config import get_settings


async def compute_live_feedback_metrics(
    *,
    user_id: str,
    session_id: str,
    lecture_id: str,
    tenant_type: str,
    opened_at: float,
    question_count: int,
    page_entered_at: float,
    last_page_id: Any,
    nudge_fired: bool,
) -> dict[str, Any]:
    """Session-scoped metrics for the live feedback panel.

    Mastery estimate and daily-goal are dependency-gated (Flow 9 / Flow 8) —
    returned as ``null`` extension points, never fabricated.
    """
    _ = (user_id, lecture_id, tenant_type)
    settings = get_settings()
    now = time.time()
    time_on_topic_seconds = max(0, int(now - opened_at))

    stuck_threshold = int(settings.STUCK_NUDGE_SECONDS)
    on_same_page = last_page_id is not None
    seconds_on_page = max(0, int(now - page_entered_at)) if on_same_page else 0
    should_nudge = (
        on_same_page
        and seconds_on_page >= stuck_threshold
        and question_count == 0
        and not nudge_fired
    )

    return {
        "session_id": session_id,
        "time_on_topic_seconds": time_on_topic_seconds,
        "questions_asked_this_session": question_count,
        # BLOCKED-HOOK → Flow 9 / M-18
        "mastery_estimate": None,
        # Forward dependency → Flow 8 / M-17
        "daily_goal_status": None,
        "stuck_nudge": {
            "should_show": should_nudge,
            "seconds_on_page": seconds_on_page,
            "already_fired": nudge_fired,
        },
        "panel_visible": time_on_topic_seconds >= int(settings.LIVE_FEEDBACK_PANEL_DELAY_SECONDS),
    }
