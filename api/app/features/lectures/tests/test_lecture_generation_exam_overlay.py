"""T-120 — exam-framework overlay wiring into run_lecture_generation."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.features.lectures.exam_overlay import ExamOverlayContext
from app.features.lectures.generation import run_lecture_generation
from app.features.lectures.models import LectureStatus, LectureType, SchoolLecture
from app.infrastructure.llm.prompts.lecture_generate_v1 import LectureGenerateInput


def _fake_lecture() -> SchoolLecture:
    return SchoolLecture(
        id="lec-1",
        school_id="school-1",
        grade_subject_offering_id="offering-1",
        teacher_user_id="teacher-1",
        title="Newton's Laws",
        topic="Newton's Laws",
        lecture_type=LectureType.MAIN,
        status=LectureStatus.GENERATING,
    )


async def _fake_publish(*, event_type: str, payload: dict[str, Any]) -> None:
    return None


def test_persona_has_no_field_on_the_lecture_prompt_input() -> None:
    """Acceptance #4: Custom Persona is class-wide-forbidden, not per-student (§3.2/§8.20)."""
    assert "persona" not in LectureGenerateInput.model_fields


@pytest.mark.asyncio
async def test_relevant_framework_context_reaches_the_prompt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lecture = _fake_lecture()
    curriculum_item = MagicMock()
    curriculum_item.id = "curr-1"
    curriculum_item.title = "Curriculum Book"

    added: list[Any] = []
    session = AsyncMock()

    async def _get(model: type[Any], pk: str) -> Any:
        if model is SchoolLecture and pk == "lec-1":
            return lecture
        if pk == "curr-1":
            return curriculum_item
        return None

    session.get = AsyncMock(side_effect=_get)
    session.add = MagicMock(side_effect=lambda obj: added.append(obj))
    session.flush = AsyncMock()
    session.commit = AsyncMock()

    async def _fake_retrieve(*_a: Any, **_k: Any) -> list[dict[str, object]]:
        return [
            {"id": "c1", "score": 1.0, "payload": {"text": "Curriculum content.", "title": "Book"}}
        ]

    overlay = ExamOverlayContext(
        framework_name="Matric Punjab — Physics",
        exam_strategy_summary="Show all working for partial marks.",
        priority_topics=["Newton's Laws (priority 0.9)"],
    )

    async def _fake_load_overlay(*_a: Any, **_k: Any) -> ExamOverlayContext:
        return overlay

    captured_user_prompt: dict[str, str] = {}

    async def _fake_chat(messages: list[dict[str, str]], *_a: Any, **_k: Any) -> Any:
        captured_user_prompt["user"] = messages[1]["content"]
        yield '{"title": "T", "paragraphs": [{"text": "x", "tier": "curriculum"}]}'

    monkeypatch.setattr("app.features.lectures.generation.retrieve", _fake_retrieve)
    monkeypatch.setattr("app.features.lectures.generation._load_exam_overlay", _fake_load_overlay)
    monkeypatch.setattr("app.features.lectures.generation.stream_chat", _fake_chat)
    monkeypatch.setattr("app.features.lectures.generation.publish_lecture_event", _fake_publish)
    monkeypatch.setattr("app.features.lectures.generation.append_token", AsyncMock(return_value=1))
    monkeypatch.setattr("app.features.lectures.generation.mark_complete", AsyncMock())
    monkeypatch.setattr("app.features.lectures.generation.notify_generation_complete", AsyncMock())
    # T-124: run_lecture_generation chains a Celery task at the end — never let a
    # unit test touch a real broker.
    monkeypatch.setattr(
        "app.features.lectures.tasks.generate_lecture_teacher_tips.apply_async",
        MagicMock(),
    )

    await run_lecture_generation(
        session,
        lecture_id="lec-1",
        school_id="school-1",
        topic="Newton's Laws",
        curriculum_id="curr-1",
        reference_book_ids=[],
        teaching_mode="auto",
        teacher_user_id="teacher-1",
    )

    prompt_text = captured_user_prompt["user"]
    assert "ADDITIONAL" in prompt_text
    assert "Matric Punjab — Physics" in prompt_text
    assert "Show all working for partial marks." in prompt_text
    assert "Newton's Laws (priority 0.9)" in prompt_text


@pytest.mark.asyncio
async def test_no_overlay_leaves_prompt_clean(monkeypatch: pytest.MonkeyPatch) -> None:
    """Acceptance #3: no framework selected -> no overlay block in the prompt."""
    lecture = _fake_lecture()
    curriculum_item = MagicMock()
    curriculum_item.id = "curr-1"
    curriculum_item.title = "Curriculum Book"

    session = AsyncMock()

    async def _get(model: type[Any], pk: str) -> Any:
        if model is SchoolLecture and pk == "lec-1":
            return lecture
        if pk == "curr-1":
            return curriculum_item
        return None

    session.get = AsyncMock(side_effect=_get)
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()

    async def _fake_retrieve(*_a: Any, **_k: Any) -> list[dict[str, object]]:
        return [
            {"id": "c1", "score": 1.0, "payload": {"text": "Curriculum content.", "title": "Book"}}
        ]

    async def _fake_load_overlay(*_a: Any, **_k: Any) -> None:
        return None

    captured_user_prompt: dict[str, str] = {}

    async def _fake_chat(messages: list[dict[str, str]], *_a: Any, **_k: Any) -> Any:
        captured_user_prompt["user"] = messages[1]["content"]
        yield '{"title": "T", "paragraphs": [{"text": "x", "tier": "curriculum"}]}'

    monkeypatch.setattr("app.features.lectures.generation.retrieve", _fake_retrieve)
    monkeypatch.setattr("app.features.lectures.generation._load_exam_overlay", _fake_load_overlay)
    monkeypatch.setattr("app.features.lectures.generation.stream_chat", _fake_chat)
    monkeypatch.setattr("app.features.lectures.generation.publish_lecture_event", _fake_publish)
    monkeypatch.setattr("app.features.lectures.generation.append_token", AsyncMock(return_value=1))
    monkeypatch.setattr("app.features.lectures.generation.mark_complete", AsyncMock())
    monkeypatch.setattr("app.features.lectures.generation.notify_generation_complete", AsyncMock())
    # T-124: run_lecture_generation chains a Celery task at the end — never let a
    # unit test touch a real broker.
    monkeypatch.setattr(
        "app.features.lectures.tasks.generate_lecture_teacher_tips.apply_async",
        MagicMock(),
    )

    await run_lecture_generation(
        session,
        lecture_id="lec-1",
        school_id="school-1",
        topic="Newton's Laws",
        curriculum_id="curr-1",
        reference_book_ids=[],
        teaching_mode="auto",
        teacher_user_id="teacher-1",
    )

    assert "ADDITIONAL" not in captured_user_prompt["user"]
    assert "Exam framework" not in captured_user_prompt["user"]
