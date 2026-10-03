"""T-187 — ``flashcard.created`` publish (wire subject ``student.flashcard.created``).

Publish-only: no SRS scheduling / py-fsrs / question queue here (Flow 9, M-18).
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.lectures import events as lecture_events
from app.features.student_highlights import events as hl_events
from app.features.student_highlights.events import (
    FLASHCARD_CREATED,
    FlashcardCreatedV1,
    flashcard_created_payload,
    publish_flashcard_created,
)
from app.features.student_highlights.models import (
    SchoolStudentFlashcard,
    SchoolStudentHighlight,
)
from app.features.student_highlights.tests.pg_support import (
    make_question,
    requires_pg,
    seed_lecture,
)
from app.infrastructure.events.streams import _STREAM_SPECS


def _card(**overrides: Any) -> SchoolStudentFlashcard:
    defaults: dict[str, Any] = {
        "id": "fc-1",
        "student_user_id": "stu-1",
        "lecture_id": "lec-1",
        "concept_tag": "forces/newton-2",
        "source_highlight_id": "h-1",
        "front_text": "mass",
        "back_text": "Mass is the amount of matter.",
        "dedupe_hash": "x" * 64,
        "created_at": datetime(2026, 10, 3, 12, tzinfo=timezone.utc),
    }
    defaults.update(overrides)
    return SchoolStudentFlashcard(**defaults)


# --- subject / payload --------------------------------------------------------


def test_subject_follows_locked_taxonomy_pattern() -> None:
    # ARCH §9.3: <domain>.<entity>.<event>, lowercase, past-tense event.
    assert FLASHCARD_CREATED == "student.flashcard.created"
    assert re.fullmatch(r"[a-z_]+\.[a-z_]+\.[a-z_]+", FLASHCARD_CREATED)


def test_subject_is_captured_by_student_events_stream() -> None:
    student = next(s for s in _STREAM_SPECS if s["name"] == "student-events")
    assert any(FLASHCARD_CREATED.startswith(p.removesuffix(">")) for p in student["subjects"])


def test_payload_carries_refs_and_tenant_not_card_text() -> None:
    payload = flashcard_created_payload(_card(), school_id="school-1")
    data = payload.model_dump(mode="json")
    assert data == {
        "schema_version": 1,
        "flashcard_id": "fc-1",
        "student_user_id": "stu-1",
        "lecture_id": "lec-1",
        "concept_tag": "forces/newton-2",
        "source_highlight_id": "h-1",
        "source_type": "highlight",
        "school_id": "school-1",
        "tenant_type": "school",
        "created_at": "2026-10-03T12:00:00Z",
    }
    assert "front_text" not in data and "back_text" not in data


def test_payload_schema_rejects_unknown_fields() -> None:
    with pytest.raises(ValueError):
        FlashcardCreatedV1.model_validate(
            {**flashcard_created_payload(_card(), school_id="s").model_dump(), "extra": 1}
        )


# --- envelope / tenant tagging -----------------------------------------------


@pytest.mark.asyncio
async def test_publish_tags_envelope_with_tenant_and_student(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    publish = AsyncMock()
    monkeypatch.setattr(lecture_events, "publish", publish)

    await publish_flashcard_created(_card(), school_id="school-1")

    publish.assert_awaited_once()
    call = publish.await_args
    assert call is not None
    args, kwargs = call.args, call.kwargs
    assert args[0] == "student.flashcard.created"  # subject
    assert args[1] == "student.flashcard.created"  # event_type == subject (§9.5)
    assert args[2]["flashcard_id"] == "fc-1"
    assert kwargs["tenant_id"] == "school-1"
    assert kwargs["tenant_type"] == "school"
    assert kwargs["user_id"] == "stu-1"
    assert kwargs["lecture_id"] == "lec-1"


@pytest.mark.asyncio
async def test_publish_failure_is_swallowed(monkeypatch: pytest.MonkeyPatch) -> None:
    """Best-effort after commit: a NATS outage never fails the answer request."""
    monkeypatch.setattr(lecture_events, "publish", AsyncMock(side_effect=OSError("nats down")))
    await publish_flashcard_created(_card(), school_id="school-1")


def test_module_exposes_no_scheduling() -> None:
    # Scope guard: M-15 publishes only; Flow 9 (M-18) owns py-fsrs scheduling.
    names = set(dir(hl_events))
    assert not {n for n in names if "fsrs" in n.lower() or "schedule" in n.lower()}


# --- through the answer pipeline (real Postgres) ------------------------------


async def _highlight(pg: AsyncSession, seed: Any, question_id: str) -> None:
    pg.add(
        SchoolStudentHighlight(
            student_user_id=seed.student_id,
            lecture_id=seed.lecture_id,
            paragraph_id=seed.paragraph_id,
            paragraph_ordinal=0,
            text_range_offset=13,
            text_range_length=4,
            highlighted_text="mass",
            question_id=question_id,
            concept_tag="forces/newton-2",
        )
    )
    await pg.flush()


@requires_pg
async def test_new_card_publishes_once_after_commit(
    pg: AsyncSession, published_flashcards: AsyncMock
) -> None:
    from app.features.student_questions.answer_pipeline import _persist_answer

    seed = await seed_lecture(pg)
    q = await make_question(pg, seed)
    await _highlight(pg, seed, q.id)

    card = await _persist_answer(
        pg, question=q, answer_text="A", tags={}, next_turn_index=1, school_id=seed.school_id
    )

    assert card is not None
    published_flashcards.assert_awaited_once()
    call = published_flashcards.await_args
    assert call is not None
    args, kwargs = call.args, call.kwargs
    assert args[0].id == card.id
    assert kwargs == {"school_id": seed.school_id}


@requires_pg
async def test_duplicate_flashcard_publishes_nothing(
    pg: AsyncSession, published_flashcards: AsyncMock
) -> None:
    from app.features.student_questions.answer_pipeline import _persist_answer

    seed = await seed_lecture(pg)
    q1 = await make_question(pg, seed)
    await _highlight(pg, seed, q1.id)
    await _persist_answer(pg, question=q1, answer_text="A", tags={}, next_turn_index=1)
    q2 = await make_question(pg, seed)
    await _highlight(pg, seed, q2.id)
    dup = await _persist_answer(pg, question=q2, answer_text="A2", tags={}, next_turn_index=1)

    assert dup is None
    assert published_flashcards.await_count == 1  # idempotent: one card → one event


@requires_pg
async def test_free_form_answer_publishes_nothing(
    pg: AsyncSession, published_flashcards: AsyncMock
) -> None:
    from app.features.student_questions.answer_pipeline import _persist_answer

    seed = await seed_lecture(pg)
    q = await make_question(pg, seed, highlight_text=None)
    await _persist_answer(pg, question=q, answer_text="A", tags={}, next_turn_index=1)
    published_flashcards.assert_not_awaited()
