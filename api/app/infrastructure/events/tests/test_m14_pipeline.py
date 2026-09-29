"""T-173 / T-174 / T-175 / T-178 / T-179 / T-182 unit tests (NATS doubles)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.features.session_difficulty.angles import TEACHING_ANGLES, next_angle
from app.features.student_events.models import StudentEventTenantType
from app.infrastructure.events.consumer import ConsumerLagState, get_lag_state, reset_lag_registry
from app.infrastructure.events.publisher import _build_envelope
from app.infrastructure.events.subjects import (
    M12_TO_ARCH_ALIAS,
    STUDENT_LECTURE_QUESTION_ASKED,
    STUDENT_LECTURE_SUBJECTS,
)
from app.infrastructure.llm.session_adapter import prepend_adaptation


def test_student_lecture_subjects_cover_m14_set() -> None:
    expected = {
        "student.lecture.question_asked",
        "student.lecture.highlight_created",
        "student.lecture.session_opened",
        "student.lecture.session_closed",
        "student.lecture.scroll",
        "student.lecture.page_change",
        "student.lecture.mode_switch",
    }
    assert expected == set(STUDENT_LECTURE_SUBJECTS)


def test_m12_alias_map() -> None:
    assert M12_TO_ARCH_ALIAS["student.question.asked"] == STUDENT_LECTURE_QUESTION_ASKED
    assert M12_TO_ARCH_ALIAS["student.highlight.created"] == "student.lecture.highlight_created"


def test_envelope_includes_m14_fields() -> None:
    envelope = _build_envelope(
        event_type="student.lecture.scroll",
        payload={"lecture_id": "lec-1", "scroll_y": 10},
        tenant_id="school-1",
        tenant_type="school",
        user_id="user-1",
        session_id="sess-1",
        lecture_id="lec-1",
    )
    for key in (
        "tenant_id",
        "tenant_type",
        "user_id",
        "session_id",
        "lecture_id",
        "timestamp",
        "event_type",
        "payload",
    ):
        assert key in envelope
    assert envelope["lecture_id"] == "lec-1"
    assert envelope["timestamp"] == envelope["occurred_at"]


def test_next_angle_rotation_no_duplicates() -> None:
    tried: list[str] = []
    seen: list[str] = []
    for _ in range(len(TEACHING_ANGLES)):
        angle = next_angle(tried)
        assert angle not in tried
        tried.append(angle)
        seen.append(angle)
    assert seen == list(TEACHING_ANGLES)
    # After all tried, next_angle returns the first again.
    assert next_angle(tried) == TEACHING_ANGLES[0]


def test_prepend_adaptation_preserves_persona() -> None:
    persona_system = "PERSONA STYLE\n\nTASK PROMPT"
    adapted = prepend_adaptation("ADAPTATION STRATEGY", persona_system)
    assert adapted.startswith("ADAPTATION STRATEGY")
    assert "PERSONA STYLE" in adapted
    assert "TASK PROMPT" in adapted


@pytest.mark.asyncio
async def test_persist_student_event_routes_independent() -> None:
    from app.features.student_events.repository import persist_student_event

    added: list[Any] = []

    class _Session:
        def add(self, obj: Any) -> None:
            added.append(obj)

        async def flush(self) -> None:
            return None

    envelope = {
        "tenant_id": "ind-1",
        "tenant_type": "independent",
        "user_id": "u-ind",
        "session_id": "s1",
        "lecture_id": "l1",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": "student.lecture.question_asked",
        "payload": {"q": 1},
    }
    row_id = await persist_student_event(_Session(), envelope)  # type: ignore[arg-type]
    assert row_id
    assert len(added) == 1
    assert added[0].tenant_type is StudentEventTenantType.INDEPENDENT
    assert added[0].__tablename__ == "student_events"
    assert added[0].__table__.schema == "independent"


@pytest.mark.asyncio
async def test_persist_student_event_routes_school() -> None:
    from app.features.student_events.repository import persist_student_event

    added: list[Any] = []

    class _Session:
        def add(self, obj: Any) -> None:
            added.append(obj)

        async def flush(self) -> None:
            return None

    envelope = {
        "tenant_id": "school-1",
        "tenant_type": "school",
        "user_id": "u-1",
        "session_id": "s1",
        "lecture_id": "l1",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": "student.lecture.scroll",
        "payload": {},
    }
    await persist_student_event(_Session(), envelope)  # type: ignore[arg-type]
    assert added[0].__table__.schema == "school"
    assert added[0].tenant_type is StudentEventTenantType.SCHOOL


@pytest.mark.asyncio
async def test_live_feedback_metrics_gates_and_stuck() -> None:
    from app.features.live_feedback.metrics import compute_live_feedback_metrics

    with patch("app.features.live_feedback.metrics.get_settings") as gs:
        gs.return_value = MagicMock(
            STUCK_NUDGE_SECONDS=600,
            LIVE_FEEDBACK_PANEL_DELAY_SECONDS=120,
        )
        now = 1_000_000.0
        with patch("app.features.live_feedback.metrics.time.time", return_value=now):
            metrics = await compute_live_feedback_metrics(
                user_id="u1",
                session_id="s1",
                lecture_id="l1",
                tenant_type="school",
                opened_at=now - 180,
                question_count=0,
                page_entered_at=now - 700,
                last_page_id="p1",
                nudge_fired=False,
            )
    assert metrics["time_on_topic_seconds"] == 180
    assert metrics["questions_asked_this_session"] == 0
    assert metrics["mastery_estimate"] is None
    assert metrics["daily_goal_status"] is None
    assert metrics["panel_visible"] is True
    assert metrics["stuck_nudge"]["should_show"] is True


@pytest.mark.asyncio
async def test_stuck_nudge_suppressed_when_questions_asked() -> None:
    from app.features.live_feedback.metrics import compute_live_feedback_metrics

    with patch("app.features.live_feedback.metrics.get_settings") as gs:
        gs.return_value = MagicMock(
            STUCK_NUDGE_SECONDS=600,
            LIVE_FEEDBACK_PANEL_DELAY_SECONDS=120,
        )
        now = 1_000_000.0
        with patch("app.features.live_feedback.metrics.time.time", return_value=now):
            metrics = await compute_live_feedback_metrics(
                user_id="u1",
                session_id="s1",
                lecture_id="l1",
                tenant_type="school",
                opened_at=now - 800,
                question_count=1,
                page_entered_at=now - 700,
                last_page_id="p1",
                nudge_fired=False,
            )
    assert metrics["stuck_nudge"]["should_show"] is False


@pytest.mark.asyncio
async def test_pipeline_lag_alert_fires() -> None:
    from app.infrastructure.events.consumers.lag_monitor import check_consumer_lag

    reset_lag_registry()
    state = get_lag_state("m14-analytics")
    assert isinstance(state, ConsumerLagState)

    with (
        patch("app.infrastructure.events.consumers.lag_monitor.get_settings") as gs,
        patch(
            "app.infrastructure.events.consumers.lag_monitor.publish",
            new_callable=AsyncMock,
        ) as pub,
        patch("app.infrastructure.events.consumers.lag_monitor.async_session_factory") as factory,
        patch(
            "app.infrastructure.events.consumers.lag_monitor.notify_all_platform_admins",
            new_callable=AsyncMock,
        ) as notify,
        patch(
            "app.infrastructure.audit.log.audit",
            new_callable=AsyncMock,
        ),
    ):
        gs.return_value = MagicMock(
            EVENT_PIPELINE_LAG_SECONDS=30,
            EVENT_PIPELINE_LAG_CHECK_SECONDS=15,
        )

        class _CM:
            async def __aenter__(self) -> MagicMock:
                s = MagicMock()
                s.commit = AsyncMock()
                return s

            async def __aexit__(self, *a: object) -> None:
                return None

        factory.return_value = _CM()
        result = await check_consumer_lag("m14-analytics", lag_seconds=45.0, force_alert=True)

    assert result["alerted"] is True
    pub.assert_awaited()
    notify.assert_awaited()


@pytest.mark.asyncio
async def test_dual_publish_alias_on_question_asked() -> None:
    from app.features.lectures.events import publish_student_lecture_event

    with patch("app.features.lectures.events.publish", new_callable=AsyncMock) as pub:
        await publish_student_lecture_event(
            event_type="student.question.asked",
            payload={
                "session_id": "s1",
                "lecture_id": "l1",
                "student_user_id": "u1",
                "school_id": "sch1",
                "tenant_type": "school",
            },
        )
    subjects = [c.args[0] for c in pub.await_args_list]
    assert "student.question.asked" in subjects
    assert "student.lecture.question_asked" in subjects


@pytest.mark.asyncio
async def test_live_feedback_no_push_after_session_closed() -> None:
    from app.infrastructure.events.consumers import live_feedback as lf

    lf.reset_active_sessions()
    await lf.handle_live_feedback_event(
        {
            "event_type": "student.lecture.session_opened",
            "user_id": "u1",
            "session_id": "s1",
            "lecture_id": "l1",
            "tenant_type": "school",
            "tenant_id": "sch",
            "payload": {},
        }
    )
    assert lf.get_active_session("u1") is not None
    await lf.handle_live_feedback_event(
        {
            "event_type": "student.lecture.session_closed",
            "user_id": "u1",
            "session_id": "s1",
            "payload": {},
        }
    )
    assert lf.get_active_session("u1") is None
