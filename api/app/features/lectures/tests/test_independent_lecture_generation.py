"""Independent lecture generation pipeline + Celery task tests — T-125."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from celery.exceptions import SoftTimeLimitExceeded

from app.features.lectures.independent_generation import run_independent_lecture_generation
from app.features.lectures.independent_tasks import (
    _handle_generation_failure,
    _handle_generation_timeout,
    generate_independent_lecture,
)
from app.features.lectures.models import (
    IndependentLecture,
    IndependentLectureParagraph,
    LectureStatus,
)


def _fake_lecture() -> IndependentLecture:
    return IndependentLecture(
        id="lec-1",
        teacher_user_id="teacher-1",
        title="Newton's Laws",
        topic="Newton's Laws",
        status=LectureStatus.GENERATING,
    )


@pytest.mark.asyncio
async def test_generation_persists_version_and_paragraphs_from_reference(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lecture = _fake_lecture()
    ref_item = MagicMock()
    ref_item.id = "ref-1"
    ref_item.user_id = "teacher-1"
    ref_item.title = "My Physics Notes"

    added: list[Any] = []
    session = AsyncMock()

    async def _get(model: type[Any], pk: str) -> Any:
        if model is IndependentLecture and pk == "lec-1":
            return lecture
        if pk == "ref-1":
            return ref_item
        return None

    session.get = AsyncMock(side_effect=_get)
    session.add = MagicMock(side_effect=lambda obj: added.append(obj))
    session.flush = AsyncMock()
    session.commit = AsyncMock()

    async def _fake_retrieve(*_a: Any, **_k: Any) -> list[dict[str, object]]:
        return [
            {
                "id": "hit-1",
                "score": 1.0,
                "payload": {"library_item_id": "ref-1", "text": "Newton's first law of motion."},
            }
        ]

    async def _fake_chat(*_a: Any, **_k: Any) -> str:
        return (
            '{"title": "Newton\'s Laws", "paragraphs": ['
            '{"text": "From my notes: force.", "tier": "reference", "book_name": "My Physics Notes"}'
            "]}"
        )

    web_search_called = False

    async def _fake_web_search(*_a: Any, **_k: Any) -> list[Any]:
        nonlocal web_search_called
        web_search_called = True
        return []

    monkeypatch.setattr("app.features.lectures.independent_generation.retrieve", _fake_retrieve)
    monkeypatch.setattr("app.features.lectures.independent_generation.chat", _fake_chat)
    monkeypatch.setattr(
        "app.features.lectures.independent_generation.notify_generation_complete", AsyncMock()
    )
    monkeypatch.setattr("app.features.lectures.generation.web_search", _fake_web_search)

    version_id = await run_independent_lecture_generation(
        session,
        lecture_id="lec-1",
        user_id="teacher-1",
        topic="Newton's Laws",
        reference_content_ids=["ref-1"],
        teaching_mode="auto",
    )

    assert lecture.status == LectureStatus.READY_FOR_EDIT
    assert lecture.current_version_id == version_id
    assert lecture.title == "Newton's Laws"
    paragraphs = [o for o in added if isinstance(o, IndependentLectureParagraph)]
    assert len(paragraphs) == 1
    assert paragraphs[0].source_metadata_jsonb["tier"] == "reference"
    # Reference retrieval found content -> no escalation to web search.
    assert web_search_called is False


@pytest.mark.asyncio
async def test_generation_falls_back_to_web_when_no_references_selected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No curriculum tier exists for independents — an empty reference set
    escalates straight to the T-119 web-search tier."""
    lecture = _fake_lecture()
    session = AsyncMock()

    async def _get(model: type[Any], pk: str) -> Any:
        if model is IndependentLecture and pk == "lec-1":
            return lecture
        return None

    session.get = AsyncMock(side_effect=_get)
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()

    web_search_called = False

    async def _fake_web_search(*_a: Any, **_k: Any) -> list[Any]:
        nonlocal web_search_called
        web_search_called = True
        return []

    captured_user_prompt: dict[str, str] = {}

    async def _fake_chat(messages: list[dict[str, str]], *_a: Any, **_k: Any) -> str:
        captured_user_prompt["user"] = messages[1]["content"]
        return '{"title": "T", "paragraphs": [{"text": "x", "tier": "ai_knowledge"}]}'

    monkeypatch.setattr("app.features.lectures.independent_generation.chat", _fake_chat)
    monkeypatch.setattr(
        "app.features.lectures.independent_generation.notify_generation_complete", AsyncMock()
    )
    monkeypatch.setattr("app.features.lectures.generation.web_search", _fake_web_search)

    await run_independent_lecture_generation(
        session,
        lecture_id="lec-1",
        user_id="teacher-1",
        topic="Newton's Laws",
        reference_content_ids=[],
        teaching_mode="auto",
    )

    assert web_search_called is True
    assert "NO SOURCES FOUND" in captured_user_prompt["user"]


@pytest.mark.asyncio
async def test_generation_raises_for_unowned_lecture() -> None:
    session = AsyncMock()
    session.get = AsyncMock(return_value=None)

    with pytest.raises(ValueError, match="lecture not found"):
        await run_independent_lecture_generation(
            session,
            lecture_id="does-not-exist",
            user_id="teacher-1",
            topic="X",
            reference_content_ids=[],
            teaching_mode="auto",
        )


# --- generate_independent_lecture Celery task -------------------------------

_TASK_KWARGS: dict[str, Any] = {
    "lecture_id": "lec-1",
    "user_id": "teacher-1",
    "topic": "Newton's Laws",
    "reference_content_ids": [],
    "teaching_mode": "auto",
}


def test_task_success_path() -> None:
    task = generate_independent_lecture

    with patch(
        "app.features.lectures.independent_tasks.run_db", return_value="ver-1"
    ) as mock_run_db:
        result = task.run(**_TASK_KWARGS)

    assert result == {"lecture_id": "lec-1", "version_id": "ver-1", "status": "generated_v1"}
    mock_run_db.assert_called_once()


def test_task_soft_timeout_marks_timed_out() -> None:
    task = generate_independent_lecture

    with patch("app.features.lectures.independent_tasks.run_db") as mock_run_db:
        mock_run_db.side_effect = [SoftTimeLimitExceeded(), None]
        result = task.run(**_TASK_KWARGS)

    assert result == {"lecture_id": "lec-1", "status": "timed_out"}
    assert mock_run_db.call_count == 2


def test_task_generic_failure_marks_failed_and_reraises() -> None:
    task = generate_independent_lecture

    with patch("app.features.lectures.independent_tasks.run_db") as mock_run_db:
        mock_run_db.side_effect = [RuntimeError("LLM provider down"), None]
        with pytest.raises(RuntimeError, match="LLM provider down"):
            task.run(**_TASK_KWARGS)

    assert mock_run_db.call_count == 2


# --- T-126: audit + notify + NATS on the failure/timeout status transitions --


def _lecture_generating() -> IndependentLecture:
    return IndependentLecture(
        id="lec-1",
        teacher_user_id="teacher-1",
        title="Newton's Laws",
        topic="Newton's Laws",
        status=LectureStatus.GENERATING,
    )


@pytest.mark.asyncio
async def test_handle_generation_timeout_audits_notifies_and_publishes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lecture = _lecture_generating()
    session = AsyncMock()
    session.get = AsyncMock(return_value=lecture)

    audit_calls: list[dict[str, Any]] = []
    notify_calls: list[dict[str, Any]] = []
    published: list[dict[str, Any]] = []

    async def _spy_audit(**kwargs: Any) -> None:
        audit_calls.append(kwargs)

    async def _spy_notify(session: Any, *, lecture: Any) -> None:
        notify_calls.append({"lecture_id": lecture.id})

    async def _spy_publish(*, event_type: str, payload: dict[str, Any]) -> None:
        published.append({"event_type": event_type, "payload": payload})

    monkeypatch.setattr("app.features.lectures.independent_tasks.audit", _spy_audit)
    monkeypatch.setattr(
        "app.features.lectures.independent_tasks.notify_generation_timeout", _spy_notify
    )
    monkeypatch.setattr(
        "app.features.lectures.independent_tasks.publish_lecture_event", _spy_publish
    )

    await _handle_generation_timeout(session, "lec-1", "teacher-1")

    assert lecture.status == LectureStatus.TIMED_OUT
    assert audit_calls[0]["action"] == "lecture.generation_timed_out"
    assert audit_calls[0]["school_id"] is None
    assert notify_calls == [{"lecture_id": "lec-1"}]
    assert published[0]["payload"]["tenant_type"] == "independent"


@pytest.mark.asyncio
async def test_handle_generation_failure_audits_notifies_and_publishes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lecture = _lecture_generating()
    session = AsyncMock()
    session.get = AsyncMock(return_value=lecture)

    audit_calls: list[dict[str, Any]] = []
    notify_calls: list[dict[str, Any]] = []
    published: list[dict[str, Any]] = []

    async def _spy_audit(**kwargs: Any) -> None:
        audit_calls.append(kwargs)

    async def _spy_notify(session: Any, *, lecture: Any, error: str) -> None:
        notify_calls.append({"lecture_id": lecture.id, "error": error})

    async def _spy_publish(*, event_type: str, payload: dict[str, Any]) -> None:
        published.append({"event_type": event_type, "payload": payload})

    monkeypatch.setattr("app.features.lectures.independent_tasks.audit", _spy_audit)
    monkeypatch.setattr(
        "app.features.lectures.independent_tasks.notify_generation_failed", _spy_notify
    )
    monkeypatch.setattr(
        "app.features.lectures.independent_tasks.publish_lecture_event", _spy_publish
    )

    await _handle_generation_failure(session, "lec-1", "teacher-1", "LLM provider down")

    assert lecture.status == LectureStatus.FAILED
    assert audit_calls[0]["action"] == "lecture.generation_failed"
    assert audit_calls[0]["actor_role"] == "independent_teacher"
    assert notify_calls == [{"lecture_id": "lec-1", "error": "LLM provider down"}]
    assert published[0]["event_type"] == "lecture.generation_failed"
