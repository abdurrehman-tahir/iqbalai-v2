"""T-158 — AI answer pipeline unit tests (mocked LLM + RAG)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import ValidationError
from app.features.lectures.models import LectureStatus, LectureType, SchoolLecture
from app.features.library.school_models import LibraryContentType
from app.features.student_questions import answer_pipeline as pipeline
from app.features.student_questions.models import (
    ConversationRole,
    QuestionClassification,
    SchoolStudentQuestion,
    SchoolStudentQuestionConversation,
    StudentQuestionTenantType,
)
from app.infrastructure.llm.prompts.lecture_qa_v1 import QaChunkRef
from app.infrastructure.rag.web_search import SearchResult


def _lecture() -> SchoolLecture:
    return SchoolLecture(
        id="lec-1",
        school_id="school-1",
        grade_subject_offering_id="offering-1",
        teacher_user_id="teacher-1",
        title="Newton's Laws",
        topic="Newton's Laws",
        lecture_type=LectureType.MAIN,
        status=LectureStatus.PUBLISHED,
        current_version_id="ver-1",
    )


def _question(**kwargs: object) -> SchoolStudentQuestion:
    defaults: dict[str, object] = {
        "id": "q-1",
        "student_user_id": "stu-1",
        "session_id": "sess-1",
        "lecture_id": "lec-1",
        "tenant_type": StudentQuestionTenantType.SCHOOL,
        "question_text": "What is inertia?",
        "question_language": "en",
        "highlight_text": "An object at rest stays at rest",
        "classification": QuestionClassification.KNOWLEDGE_GAP,
        "asked_at": datetime.now(timezone.utc),
    }
    defaults.update(kwargs)
    return SchoolStudentQuestion(**defaults)


def _user_turn(
    content: str = "What is inertia?", turn_index: int = 0
) -> SchoolStudentQuestionConversation:
    return SchoolStudentQuestionConversation(
        id="turn-u-0",
        root_question_id="q-1",
        turn_index=turn_index,
        role=ConversationRole.USER,
        content=content,
    )


def test_build_source_tags_prefers_curriculum() -> None:
    primary, tags = pipeline.build_source_tags(
        curriculum=[
            QaChunkRef(
                source_id="c1",
                source_label="Phys Curr",
                tier="curriculum",
                text="Inertia is resistance to change in motion.",
            )
        ],
        reference=[],
        web=[],
        no_coverage=False,
    )
    assert primary == "[Curriculum]"
    assert tags[0]["tier"] == "curriculum"
    assert tags[0]["chunk_id"] == "c1"


def test_build_source_tags_no_coverage_includes_web_stub_and_no_source() -> None:
    primary, tags = pipeline.build_source_tags(
        curriculum=[],
        reference=[],
        web=[],
        no_coverage=True,
    )
    assert primary == "[Web]"
    tiers = {t["tier"] for t in tags}
    assert tiers == {"web", "no_source", "ai_knowledge"}
    assert any("unavailable" in str(t.get("excerpt", "")).lower() for t in tags)


@pytest.mark.asyncio
async def test_retrieve_qa_chunks_uses_pattern_s_then_web(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lecture = _lecture()
    session = AsyncMock()

    curr_item = MagicMock()
    curr_item.id = "curr-1"
    curr_item.title = "Curriculum"
    curr_item.content_type = LibraryContentType.CURRICULUM

    async def _resolve(_session: Any, _lec: SchoolLecture) -> tuple[list[Any], list[Any]]:
        return [curr_item], []

    async def _retrieve(**_kwargs: Any) -> list[dict[str, Any]]:
        return []

    async def _db_chunks(_session: Any, item_ids: list[str]) -> list[Any]:
        chunk = MagicMock()
        chunk.id = "chunk-1"
        chunk.library_item_id = "curr-1"
        chunk.chunk_index = 0
        chunk.chunk_text = "Inertia means an object resists changes to its motion."
        return [chunk]

    monkeypatch.setattr(pipeline, "resolve_lecture_corpus", _resolve)
    monkeypatch.setattr(pipeline, "_retrieve_for_items", _retrieve)
    monkeypatch.setattr(pipeline, "_load_db_chunks", _db_chunks)

    curr, ref, web, no_coverage = await pipeline.retrieve_qa_chunks(
        session, lecture=lecture, query="What is inertia?"
    )
    assert no_coverage is False
    assert len(curr) == 1
    assert curr[0].tier == "curriculum"
    assert ref == []
    assert web == []


@pytest.mark.asyncio
async def test_retrieve_qa_chunks_web_fallback_when_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lecture = _lecture()
    session = AsyncMock()

    async def _resolve(_session: Any, _lec: SchoolLecture) -> tuple[list[Any], list[Any]]:
        return [], []

    async def _retrieve(**_kwargs: Any) -> list[dict[str, Any]]:
        return []

    async def _web(topic: str) -> list[Any]:
        return [
            QaChunkRef(
                source_id="https://example.com/inertia",
                source_label="Inertia (web)",
                tier="web",
                text="Web explanation of inertia.",
            )
        ]

    monkeypatch.setattr(pipeline, "resolve_lecture_corpus", _resolve)
    monkeypatch.setattr(pipeline, "_retrieve_for_items", _retrieve)
    monkeypatch.setattr(pipeline, "_fetch_web_fallback_chunks", _web)

    curr, ref, web, no_coverage = await pipeline.retrieve_qa_chunks(
        session, lecture=lecture, query="obscure topic"
    )
    assert curr == []
    assert ref == []
    assert len(web) == 1
    assert web[0].tier == "web"
    assert no_coverage is False


@pytest.mark.asyncio
async def test_stream_answer_persists_assistant_turn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lecture = _lecture()
    question = _question()
    turns = [_user_turn()]
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    added: list[Any] = []
    session.add = MagicMock(side_effect=lambda obj: added.append(obj))

    async def _retrieve(
        _session: Any,
        *,
        lecture: SchoolLecture,
        query: str,
        skip_web_fallback: bool = False,
    ) -> tuple[list[QaChunkRef], list[QaChunkRef], list[QaChunkRef], bool]:
        return (
            [
                QaChunkRef(
                    source_id="c1",
                    source_label="Phys Curr",
                    tier="curriculum",
                    text="Inertia is resistance to change.",
                )
            ],
            [],
            [],
            False,
        )

    async def _persona(*_a: Any, **_k: Any) -> str:
        return "You are a warm tutor."

    async def _fake_stream(*_a: Any, **_k: Any) -> Any:
        for part in ("Inertia ", "is resistance ", "to change. [Curriculum]"):
            yield part

    monkeypatch.setattr(pipeline, "retrieve_qa_chunks", _retrieve)
    monkeypatch.setattr(pipeline, "resolve_base_persona", _persona)
    monkeypatch.setattr(pipeline, "stream_chat", _fake_stream)
    monkeypatch.setattr(
        pipeline, "get_student_exam_framework_overlay", AsyncMock(return_value=None)
    )
    # Avoid ORM lookups for T-161 overlay resolution in this unit test.
    session.get = AsyncMock(return_value=None)

    tokens: list[str] = []
    async for tok in pipeline.stream_answer_for_question(
        session, question=question, lecture=lecture, turns=turns
    ):
        tokens.append(tok)

    assert "".join(tokens) == "Inertia is resistance to change. [Curriculum]"
    assert question.answer_text is not None
    assert "Inertia" in question.answer_text
    assert question.answered_at is not None
    assert isinstance(question.answer_source_tags_jsonb, dict)
    assert question.answer_source_tags_jsonb["primary_badge"] == "[Curriculum]"
    assert len(added) == 1
    assert added[0].role == ConversationRole.ASSISTANT
    assert added[0].turn_index == 1
    session.commit.assert_awaited()


@pytest.mark.asyncio
async def test_stream_answer_replays_stored_when_already_answered(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lecture = _lecture()
    question = _question(
        answer_text="Already answered. [Curriculum]",
        answered_at=datetime.now(timezone.utc),
    )
    turns = [
        _user_turn(),
        SchoolStudentQuestionConversation(
            id="turn-a-1",
            root_question_id="q-1",
            turn_index=1,
            role=ConversationRole.ASSISTANT,
            content="Already answered. [Curriculum]",
        ),
    ]
    session = AsyncMock()

    called = {"stream": False}

    async def _fake_stream(*_a: Any, **_k: Any) -> Any:
        called["stream"] = True
        yield "should-not-run"
        return
        yield  # pragma: no cover

    monkeypatch.setattr(pipeline, "stream_chat", _fake_stream)

    tokens: list[str] = []
    async for tok in pipeline.stream_answer_for_question(
        session, question=question, lecture=lecture, turns=turns
    ):
        tokens.append(tok)

    assert tokens == ["Already answered. [Curriculum]"]
    assert called["stream"] is False
    session.commit.assert_not_called()


def test_collect_attached_images_merges_question_and_latest_user_turn() -> None:
    question = _question(
        attached_images_jsonb=[
            {
                "storage_key": "student-question-image/s/2026/01/01/u1/a.jpg",
                "mime_type": "image/jpeg",
                "size_bytes": 10,
            }
        ]
    )
    turns = [
        _user_turn(),
        SchoolStudentQuestionConversation(
            id="turn-a-1",
            root_question_id="q-1",
            turn_index=1,
            role=ConversationRole.ASSISTANT,
            content="answer",
        ),
        SchoolStudentQuestionConversation(
            id="turn-u-2",
            root_question_id="q-1",
            turn_index=2,
            role=ConversationRole.USER,
            content="follow up",
            attached_images_jsonb=[
                {
                    "storage_key": "student-question-image/s/2026/01/02/u2/b.jpg",
                    "mime_type": "image/jpeg",
                    "size_bytes": 20,
                }
            ],
        ),
    ]
    keys = pipeline.collect_attached_images(question, turns)
    assert keys == [
        "student-question-image/s/2026/01/01/u1/a.jpg",
        "student-question-image/s/2026/01/02/u2/b.jpg",
    ]


def test_collect_attached_images_caps_at_three() -> None:
    question = _question(
        attached_images_jsonb=[
            {"storage_key": f"k{i}", "mime_type": "image/jpeg", "size_bytes": 1} for i in range(3)
        ]
    )
    turns = [
        SchoolStudentQuestionConversation(
            id="turn-u-0",
            root_question_id="q-1",
            turn_index=0,
            role=ConversationRole.USER,
            content="q",
            attached_images_jsonb=[
                {"storage_key": "k-extra", "mime_type": "image/jpeg", "size_bytes": 1}
            ],
        )
    ]
    keys = pipeline.collect_attached_images(question, turns)
    assert len(keys) == 3
    assert keys == ["k0", "k1", "k2"]


def test_collect_attached_images_none_when_no_images() -> None:
    question = _question()
    assert pipeline.collect_attached_images(question, [_user_turn()]) == []


@pytest.mark.asyncio
async def test_enforce_vision_cost_guard_allows_under_ceiling(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_redis = AsyncMock()
    fake_redis.incr = AsyncMock(return_value=1)
    fake_redis.expire = AsyncMock(return_value=True)
    monkeypatch.setattr("app.infrastructure.cache.client.get_redis", lambda: fake_redis)
    await pipeline.enforce_vision_cost_guard("stu-1")
    fake_redis.incr.assert_awaited()


@pytest.mark.asyncio
async def test_enforce_vision_cost_guard_blocks_over_ceiling(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_redis = AsyncMock()
    fake_redis.incr = AsyncMock(return_value=21)  # > default ceiling of 20
    monkeypatch.setattr("app.infrastructure.cache.client.get_redis", lambda: fake_redis)
    with pytest.raises(ValidationError) as exc_info:
        await pipeline.enforce_vision_cost_guard("stu-1")
    assert "limit" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_enforce_vision_cost_guard_fails_open_when_redis_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _raise() -> Any:
        raise ConnectionError("redis down")

    monkeypatch.setattr("app.infrastructure.cache.client.get_redis", _raise)
    # Must not raise — a cache outage should never block Q&A.
    await pipeline.enforce_vision_cost_guard("stu-1")


@pytest.mark.asyncio
async def test_audit_vision_routed_writes_audit_entry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lecture = _lecture()
    question = _question()
    session = AsyncMock()
    added: list[Any] = []
    session.add = MagicMock(side_effect=lambda obj: added.append(obj))
    session.commit = AsyncMock()

    await pipeline._audit_vision_routed(session, question=question, lecture=lecture, image_count=2)

    assert len(added) == 1
    entry = added[0]
    assert entry.action == "llm.vision_routed"
    assert entry.actor_id == question.student_user_id
    assert entry.metadata_json == '{"image_count": 2}'


@pytest.mark.asyncio
async def test_audit_vision_routed_never_raises_on_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lecture = _lecture()
    question = _question()
    session = AsyncMock()
    session.add = MagicMock(side_effect=RuntimeError("db down"))

    # Must not raise — audit failures must never block Q&A.
    await pipeline._audit_vision_routed(session, question=question, lecture=lecture, image_count=1)


@pytest.mark.asyncio
async def test_retrieve_qa_chunks_skips_web_fallback_when_images_attached(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T-169: pure-vision reasoning (no RAG, images present) → no web fallback,
    so build_source_tags lands on [AI Knowledge] rather than [Web]/[No Source]."""
    lecture = _lecture()
    session = AsyncMock()

    async def _resolve(_session: Any, _lec: SchoolLecture) -> tuple[list[Any], list[Any]]:
        return [], []

    async def _retrieve(**_kwargs: Any) -> list[dict[str, Any]]:
        return []

    web_called = {"called": False}

    async def _web(_topic: str) -> list[Any]:
        web_called["called"] = True
        return []

    monkeypatch.setattr(pipeline, "resolve_lecture_corpus", _resolve)
    monkeypatch.setattr(pipeline, "_retrieve_for_items", _retrieve)
    monkeypatch.setattr(pipeline, "_fetch_web_fallback_chunks", _web)

    curr, ref, web, no_coverage = await pipeline.retrieve_qa_chunks(
        session, lecture=lecture, query="what is this?", skip_web_fallback=True
    )
    assert curr == []
    assert ref == []
    assert web == []
    assert no_coverage is False
    assert web_called["called"] is False

    primary, _tags = pipeline.build_source_tags(
        curriculum=curr, reference=ref, web=web, no_coverage=no_coverage
    )
    assert primary == "[AI Knowledge]"


@pytest.mark.asyncio
async def test_stream_answer_passes_attached_images_to_stream_chat(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lecture = _lecture()
    question = _question(
        attached_images_jsonb=[
            {
                "storage_key": "student-question-image/s/2026/01/01/u1/a.jpg",
                "mime_type": "image/jpeg",
                "size_bytes": 10,
            }
        ]
    )
    turns = [_user_turn()]
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()

    async def _retrieve(
        _session: Any, *, lecture: SchoolLecture, query: str, skip_web_fallback: bool = False
    ) -> tuple[list[Any], list[Any], list[Any], bool]:
        assert skip_web_fallback is True
        return [], [], [], False

    captured: dict[str, Any] = {}

    async def _fake_stream(*_a: Any, **kwargs: Any) -> Any:
        captured["attached_images"] = kwargs.get("attached_images")
        yield "It shows a force diagram. [AI Knowledge]"

    async def _persona(*_a: Any, **_k: Any) -> str:
        return "You are a warm tutor."

    monkeypatch.setattr(pipeline, "retrieve_qa_chunks", _retrieve)
    monkeypatch.setattr(pipeline, "resolve_base_persona", _persona)
    monkeypatch.setattr(pipeline, "stream_chat", _fake_stream)
    monkeypatch.setattr(pipeline, "_audit_vision_routed", AsyncMock())
    monkeypatch.setattr(
        pipeline, "get_student_exam_framework_overlay", AsyncMock(return_value=None)
    )
    session.get = AsyncMock(return_value=None)

    tokens: list[str] = []
    async for tok in pipeline.stream_answer_for_question(
        session, question=question, lecture=lecture, turns=turns
    ):
        tokens.append(tok)

    assert captured["attached_images"] == ["student-question-image/s/2026/01/01/u1/a.jpg"]


@pytest.mark.asyncio
async def test_fetch_web_via_generation_helper_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Smoke: Pattern A SearXNG primitives remain reachable for empty corpus."""

    async def _fake_web_search(query: str, max_results: int = 15) -> list[SearchResult]:
        return [SearchResult(title="T", url="https://example.com/t", snippet="...")]

    async def _fake_web_fetch(url: str) -> str:
        return "Fetched web body about the topic."

    monkeypatch.setattr(pipeline, "web_search", _fake_web_search)
    monkeypatch.setattr(pipeline, "web_fetch", _fake_web_fetch)

    chunks = await pipeline._fetch_web_fallback_chunks("topic")
    assert len(chunks) == 1
    assert chunks[0].tier == "web"
