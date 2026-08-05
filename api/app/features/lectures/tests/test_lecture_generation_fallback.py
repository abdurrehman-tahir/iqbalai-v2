"""T-119 (#27) — 3-tier out-of-curriculum fallback: reference → SearXNG web → "no info"."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.features.lectures.generation import _fetch_web_fallback_chunks, run_lecture_generation
from app.features.lectures.models import (
    LectureStatus,
    LectureType,
    SchoolLecture,
    SchoolLectureParagraph,
)
from app.infrastructure.llm.prompts.lecture_generate_v1 import NO_COVERAGE_NOTICE
from app.infrastructure.rag.web_search import SearchResult


def _fake_lecture() -> SchoolLecture:
    return SchoolLecture(
        id="lec-1",
        school_id="school-1",
        grade_subject_offering_id="offering-1",
        teacher_user_id="teacher-1",
        title="Quantum Foam",
        topic="Quantum Foam",
        lecture_type=LectureType.MAIN,
        status=LectureStatus.GENERATING,
    )


def _fake_session(lecture: SchoolLecture) -> tuple[AsyncMock, list[Any]]:
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
    return session, added


async def _fake_publish(*, event_type: str, payload: dict[str, Any]) -> None:
    return None


@pytest.mark.asyncio
async def test_fetch_web_fallback_chunks_returns_fetched_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _fake_web_search(query: str, max_results: int = 15) -> list[SearchResult]:
        return [SearchResult(title="Quantum Foam", url="https://example.com/qf", snippet="...")]

    async def _fake_web_fetch(url: str) -> str:
        return "Quantum foam is a concept in quantum mechanics..."

    monkeypatch.setattr("app.features.lectures.generation.web_search", _fake_web_search)
    monkeypatch.setattr("app.features.lectures.generation.web_fetch", _fake_web_fetch)

    chunks = await _fetch_web_fallback_chunks("Quantum Foam")

    assert len(chunks) == 1
    assert chunks[0].tier == "web"
    assert chunks[0].source_id == "https://example.com/qf"
    assert "Quantum foam is a concept" in chunks[0].text


@pytest.mark.asyncio
async def test_fetch_web_fallback_chunks_empty_when_fetch_returns_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _fake_web_search(query: str, max_results: int = 15) -> list[SearchResult]:
        return [SearchResult(title="X", url="https://example.com/x", snippet="...")]

    async def _fake_web_fetch(url: str) -> str:
        return ""  # web_fetch's own contract: "" on failure, never raises

    monkeypatch.setattr("app.features.lectures.generation.web_search", _fake_web_search)
    monkeypatch.setattr("app.features.lectures.generation.web_fetch", _fake_web_fetch)

    assert await _fetch_web_fallback_chunks("Quantum Foam") == []


@pytest.mark.asyncio
async def test_fetch_web_fallback_chunks_handles_searxng_outage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _raising_web_search(query: str, max_results: int = 15) -> list[SearchResult]:
        raise httpx.ConnectError("searxng unreachable")

    monkeypatch.setattr("app.features.lectures.generation.web_search", _raising_web_search)

    assert await _fetch_web_fallback_chunks("Quantum Foam") == []


@pytest.mark.asyncio
async def test_curriculum_covered_topic_never_calls_web_search(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Acceptance #1: curriculum-covered segment uses curriculum — no fallback triggered."""
    lecture = _fake_lecture()
    session, _added = _fake_session(lecture)

    async def _fake_retrieve(*_a: Any, **_k: Any) -> list[dict[str, object]]:
        return [
            {"id": "c1", "score": 1.0, "payload": {"text": "Curriculum content.", "title": "Book"}}
        ]

    web_search_called = False

    async def _fake_web_search(*_a: Any, **_k: Any) -> list[SearchResult]:
        nonlocal web_search_called
        web_search_called = True
        return []

    async def _fake_chat(*_a: Any, **_k: Any) -> Any:
        yield '{"title": "T", "paragraphs": [{"text": "x", "tier": "curriculum"}]}'

    monkeypatch.setattr("app.features.lectures.generation.retrieve", _fake_retrieve)
    monkeypatch.setattr("app.features.lectures.generation.web_search", _fake_web_search)
    monkeypatch.setattr("app.features.lectures.generation.stream_chat", _fake_chat)
    monkeypatch.setattr("app.features.lectures.generation.publish_lecture_event", _fake_publish)
    monkeypatch.setattr("app.features.lectures.generation.append_token", AsyncMock(return_value=1))
    monkeypatch.setattr("app.features.lectures.generation.mark_complete", AsyncMock())
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
        topic="Quantum Foam",
        curriculum_id="curr-1",
        reference_book_ids=[],
        teaching_mode="auto",
        teacher_user_id="teacher-1",
    )

    assert web_search_called is False


@pytest.mark.asyncio
async def test_curriculum_empty_reference_covered_escalates_to_reference_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Acceptance #2: curriculum empty but reference covers it — tier 2, no web call."""
    lecture = _fake_lecture()
    ref_item = MagicMock()
    ref_item.id = "ref-1"
    ref_item.title = "Physics Today"

    added: list[Any] = []
    session = AsyncMock()

    async def _get(model: type[Any], pk: str) -> Any:
        if model is SchoolLecture and pk == "lec-1":
            return lecture
        if pk == "curr-1":
            return None  # curriculum item not found → curriculum tier empty
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
                "id": "r1",
                "score": 1.0,
                "payload": {"text": "Reference content.", "title": "Physics Today"},
            }
        ]

    web_search_called = False

    async def _fake_web_search(*_a: Any, **_k: Any) -> list[SearchResult]:
        nonlocal web_search_called
        web_search_called = True
        return []

    captured_user_prompt: dict[str, str] = {}

    async def _fake_chat(messages: list[dict[str, str]], *_a: Any, **_k: Any) -> Any:
        captured_user_prompt["user"] = messages[1]["content"]
        yield (
            '{"title": "T", "paragraphs": '
            '[{"text": "From ref.", "tier": "reference", "book_name": "Physics Today"}]}'
        )

    monkeypatch.setattr("app.features.lectures.generation.retrieve", _fake_retrieve)
    monkeypatch.setattr("app.features.lectures.generation.web_search", _fake_web_search)
    monkeypatch.setattr("app.features.lectures.generation.stream_chat", _fake_chat)
    monkeypatch.setattr("app.features.lectures.generation.publish_lecture_event", _fake_publish)
    monkeypatch.setattr("app.features.lectures.generation.append_token", AsyncMock(return_value=1))
    monkeypatch.setattr("app.features.lectures.generation.mark_complete", AsyncMock())
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
        topic="Quantum Foam",
        curriculum_id="curr-1",
        reference_book_ids=["ref-1"],
        teaching_mode="auto",
        teacher_user_id="teacher-1",
    )

    assert web_search_called is False
    assert "[Ref: Physics Today" in captured_user_prompt["user"]
    paragraphs = [o for o in added if isinstance(o, SchoolLectureParagraph)]
    assert paragraphs[0].source_metadata_jsonb["tier"] == "reference"


@pytest.mark.asyncio
async def test_uncovered_topic_escalates_to_web_and_tags_paragraph(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Acceptance #2/#3/#5: curriculum+reference empty → web search → web-tagged paragraph."""
    lecture = _fake_lecture()
    session, added = _fake_session(lecture)

    async def _empty_retrieve(*_a: Any, **_k: Any) -> list[dict[str, object]]:
        return []

    async def _empty_db_chunks(_session: Any, item_ids: list[str]) -> list[Any]:
        return []

    async def _fake_web_search(query: str, max_results: int = 15) -> list[SearchResult]:
        return [SearchResult(title="Quantum Foam", url="https://example.com/qf", snippet="...")]

    async def _fake_web_fetch(url: str) -> str:
        return "Web content about quantum foam."

    captured_user_prompt: dict[str, str] = {}

    async def _fake_chat(messages: list[dict[str, str]], *_a: Any, **_k: Any) -> Any:
        captured_user_prompt["user"] = messages[1]["content"]
        yield (
            '{"title": "Quantum Foam", "paragraphs": '
            '[{"text": "From the web.", "tier": "web", "chunk_id": "https://example.com/qf"}]}'
        )

    monkeypatch.setattr("app.features.lectures.generation.retrieve", _empty_retrieve)
    monkeypatch.setattr("app.features.lectures.generation._load_db_chunks", _empty_db_chunks)
    monkeypatch.setattr("app.features.lectures.generation.web_search", _fake_web_search)
    monkeypatch.setattr("app.features.lectures.generation.web_fetch", _fake_web_fetch)
    monkeypatch.setattr("app.features.lectures.generation.stream_chat", _fake_chat)
    monkeypatch.setattr("app.features.lectures.generation.publish_lecture_event", _fake_publish)
    monkeypatch.setattr("app.features.lectures.generation.append_token", AsyncMock(return_value=1))
    monkeypatch.setattr("app.features.lectures.generation.mark_complete", AsyncMock())
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
        topic="Quantum Foam",
        curriculum_id="curr-1",
        reference_book_ids=[],
        teaching_mode="auto",
        teacher_user_id="teacher-1",
    )

    assert "[Web: Quantum Foam" in captured_user_prompt["user"]
    assert NO_COVERAGE_NOTICE not in captured_user_prompt["user"]
    paragraphs = [o for o in added if isinstance(o, SchoolLectureParagraph)]
    assert paragraphs[0].source_metadata_jsonb["tier"] == "web"


@pytest.mark.asyncio
async def test_all_tiers_empty_injects_no_coverage_notice(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Acceptance #4: curriculum+reference+web all empty → honest 'no information' notice."""
    lecture = _fake_lecture()
    session, added = _fake_session(lecture)

    async def _empty_retrieve(*_a: Any, **_k: Any) -> list[dict[str, object]]:
        return []

    async def _empty_db_chunks(_session: Any, item_ids: list[str]) -> list[Any]:
        return []

    async def _empty_web_search(query: str, max_results: int = 15) -> list[SearchResult]:
        return []

    captured_user_prompt: dict[str, str] = {}

    async def _fake_chat(messages: list[dict[str, str]], *_a: Any, **_k: Any) -> Any:
        captured_user_prompt["user"] = messages[1]["content"]
        yield (
            '{"title": "Quantum Foam", "paragraphs": '
            '[{"text": "I don\'t have information on this topic.", "tier": "ai_knowledge"}]}'
        )

    monkeypatch.setattr("app.features.lectures.generation.retrieve", _empty_retrieve)
    monkeypatch.setattr("app.features.lectures.generation._load_db_chunks", _empty_db_chunks)
    monkeypatch.setattr("app.features.lectures.generation.web_search", _empty_web_search)
    monkeypatch.setattr("app.features.lectures.generation.stream_chat", _fake_chat)
    monkeypatch.setattr("app.features.lectures.generation.publish_lecture_event", _fake_publish)
    monkeypatch.setattr("app.features.lectures.generation.append_token", AsyncMock(return_value=1))
    monkeypatch.setattr("app.features.lectures.generation.mark_complete", AsyncMock())
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
        topic="Quantum Foam",
        curriculum_id="curr-1",
        reference_book_ids=[],
        teaching_mode="auto",
        teacher_user_id="teacher-1",
    )

    assert NO_COVERAGE_NOTICE in captured_user_prompt["user"]
    paragraphs = [o for o in added if isinstance(o, SchoolLectureParagraph)]
    assert paragraphs[0].source_metadata_jsonb["tier"] == "ai_knowledge"
    assert "don't have information" in paragraphs[0].text
