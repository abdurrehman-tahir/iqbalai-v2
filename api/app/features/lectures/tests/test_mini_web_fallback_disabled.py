"""T-198 — mini-lecture path disables SearXNG web fallback."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.features.lectures.models import LectureStatus, LectureType, SchoolLecture


@pytest.mark.asyncio
async def test_allow_web_fallback_false_skips_searxng(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.features.lectures import generation as gen

    web_called = False

    async def _fake_web(*_a: Any, **_k: Any) -> list[Any]:
        nonlocal web_called
        web_called = True
        return []

    monkeypatch.setattr(gen, "web_search", _fake_web)
    monkeypatch.setattr(gen, "_retrieve_for_items", AsyncMock(return_value=[]))
    monkeypatch.setattr(gen, "_load_exam_overlay", AsyncMock(return_value=None))
    monkeypatch.setattr(gen, "publish_lecture_event", AsyncMock())
    monkeypatch.setattr(gen, "append_token", AsyncMock())
    monkeypatch.setattr(gen, "mark_complete", AsyncMock())
    monkeypatch.setattr(gen, "notify_generation_complete", AsyncMock())
    monkeypatch.setattr(gen, "audit", AsyncMock())

    async def _fake_stream(*_a: Any, **_k: Any) -> Any:
        payload = (
            '{"title": "Mini", "paragraphs": [{"text": "'
            + ("word " * 50)
            + '", "tier": "ai_knowledge"}]}'
        )
        yield payload

    monkeypatch.setattr(gen, "stream_chat", _fake_stream)

    async def _fake_coaching(*_a: Any, **_k: Any) -> list[str]:
        return []

    monkeypatch.setattr(
        "app.features.teacher_coaching.service.get_generation_coaching_context_school",
        _fake_coaching,
    )
    # Generation enqueues tips + scoring; CI has no Redis on :6379.
    monkeypatch.setattr(
        "app.features.lectures.tasks.generate_lecture_teacher_tips.apply_async",
        MagicMock(),
    )
    monkeypatch.setattr(
        "app.features.lectures.tasks.score_lecture_version.apply_async",
        MagicMock(),
    )

    lecture = SchoolLecture(
        id="lec-mini",
        school_id="sch-1",
        teacher_user_id="t1",
        title="t",
        topic="topic",
        lecture_type=LectureType.MINI,
        parent_lecture_id="parent-1",
        status=LectureStatus.GENERATING,
    )

    session = MagicMock()
    session.get = AsyncMock(side_effect=[lecture, None])  # lecture, curriculum None
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()

    await gen.run_lecture_generation(
        session,
        lecture_id="lec-mini",
        school_id="sch-1",
        topic="topic",
        curriculum_id="missing",
        reference_book_ids=[],
        teaching_mode="auto",
        teacher_user_id="t1",
        allow_web_fallback=False,
    )

    assert web_called is False
