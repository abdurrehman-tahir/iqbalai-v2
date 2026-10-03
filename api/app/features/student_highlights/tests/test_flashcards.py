"""T-186 — auto-flashcard generation (flow-6 §3.6 / §5.5)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Base, SoftDeleteMixin
from app.features.student_highlights.flashcards import (
    ensure_flashcard_for_highlight,
    flashcard_dedupe_hash,
    normalise_highlight_text,
)
from app.features.student_highlights.models import (
    FlashcardSourceType,
    FlashcardStatus,
    HighlightTenantType,
    SchoolStudentFlashcard,
    SchoolStudentHighlight,
)
from app.features.student_highlights.tests.pg_support import (
    Seed,
    make_question,
    now,
    requires_pg,
    seed_lecture,
)

_MIGRATION = (
    Path(__file__).resolve().parents[4]
    / "alembic"
    / "versions"
    / "school"
    / "0074_student_flashcards.py"
)


# --- pure ---------------------------------------------------------------------


def test_dedupe_hash_is_stable_and_whitespace_case_insensitive() -> None:
    a = flashcard_dedupe_hash(highlight_text="Newton's  second\nlaw", lecture_id="lec-1")
    b = flashcard_dedupe_hash(highlight_text="  newton's second law ", lecture_id="lec-1")
    assert a == b
    assert len(a) == 64


def test_dedupe_hash_differs_per_lecture_and_text() -> None:
    base = flashcard_dedupe_hash(highlight_text="mass", lecture_id="lec-1")
    assert base != flashcard_dedupe_hash(highlight_text="mass", lecture_id="lec-2")
    assert base != flashcard_dedupe_hash(highlight_text="force", lecture_id="lec-1")


def test_dedupe_hash_separator_prevents_boundary_collisions() -> None:
    assert flashcard_dedupe_hash(highlight_text="bc", lecture_id="a") != flashcard_dedupe_hash(
        highlight_text="c", lecture_id="ab"
    )


def test_normalise_collapses_whitespace() -> None:
    assert normalise_highlight_text("  A\t B \n") == "a b"


def test_flashcard_table_shape() -> None:
    table = Base.metadata.tables["school.student_flashcards"]
    cols = {c.name for c in table.columns}
    assert {
        "id",
        "student_user_id",
        "lecture_id",
        "concept_tag",
        "front_text",
        "back_text",
        "dedupe_hash",
        "created_at",
        "tenant_type",
        "source_highlight_id",
        "status",
    } <= cols
    assert issubclass(SchoolStudentFlashcard, SoftDeleteMixin)
    fks = {fk.parent.name: fk.ondelete for fk in table.foreign_keys}
    # Card survives its highlight (§5.5) and its lecture.
    assert fks["source_highlight_id"] == "SET NULL"
    assert fks["lecture_id"] == "SET NULL"
    uq = next(i for i in table.indexes if i.name == "student_flashcards_student_dedupe_uq")
    assert uq.unique and [c.name for c in uq.columns] == ["student_user_id", "dedupe_hash"]
    # No SRS state in M-15 (Flow 8/9 own scheduling).
    assert not {"due_at", "stability", "difficulty", "last_reviewed_at"} & cols


def test_migration_revises_0073() -> None:
    text = _MIGRATION.read_text(encoding="utf-8")
    assert 'revision: str = "school_0074"' in text
    assert 'down_revision: str = "school_0073"' in text
    assert "deleted_at IS NULL" in text


# --- real Postgres ------------------------------------------------------------


async def _highlight(
    pg: AsyncSession, seed: Seed, question_id: str, **kw: Any
) -> SchoolStudentHighlight:
    row = SchoolStudentHighlight(
        student_user_id=kw.get("student_id", seed.student_id),
        lecture_id=seed.lecture_id,
        lecture_version_id=seed.version_id,
        paragraph_id=seed.paragraph_id,
        paragraph_ordinal=0,
        text_range_offset=kw.get("offset", 13),
        text_range_length=len(kw.get("text", "mass")),
        highlighted_text=kw.get("text", "mass"),
        question_id=question_id,
        concept_tag="forces/newton-2",
    )
    pg.add(row)
    await pg.flush()
    return row


async def _count_cards(pg: AsyncSession, student_id: str) -> int:
    result = await pg.execute(
        select(func.count())
        .select_from(SchoolStudentFlashcard)
        .where(SchoolStudentFlashcard.student_user_id == student_id)
    )
    return int(result.scalar_one())


@requires_pg
async def test_creates_card_with_front_back_tags(pg: AsyncSession) -> None:
    seed = await seed_lecture(pg)
    q = await make_question(pg, seed)
    hl = await _highlight(pg, seed, q.id)

    card, created = await ensure_flashcard_for_highlight(
        pg, highlight=hl, answer_text="Mass is the amount of matter.", answer_ok=True
    )
    await pg.commit()

    assert created is True
    assert card.front_text == "mass"
    assert card.back_text == "Mass is the amount of matter."
    assert card.lecture_id == seed.lecture_id
    assert card.concept_tag == "forces/newton-2"
    assert card.student_user_id == seed.student_id
    assert card.tenant_type == HighlightTenantType.SCHOOL
    assert card.source_type == FlashcardSourceType.HIGHLIGHT
    assert card.status == FlashcardStatus.ACTIVE
    assert card.source_highlight_id == hl.id


@requires_pg
async def test_duplicate_highlight_reuses_card(pg: AsyncSession) -> None:
    seed = await seed_lecture(pg)
    q1 = await make_question(pg, seed)
    q2 = await make_question(pg, seed)
    first, created1 = await ensure_flashcard_for_highlight(
        pg, highlight=await _highlight(pg, seed, q1.id), answer_text="A1", answer_ok=True
    )
    # Same text, different whitespace/case → same dedupe hash → reuse.
    second, created2 = await ensure_flashcard_for_highlight(
        pg,
        highlight=await _highlight(pg, seed, q2.id, text="MASS"),
        answer_text="A2",
        answer_ok=True,
    )
    assert created1 is True and created2 is False
    assert second.id == first.id
    assert await _count_cards(pg, seed.student_id) == 1


@requires_pg
async def test_other_student_same_text_gets_own_card(pg: AsyncSession) -> None:
    seed = await seed_lecture(pg)
    q1 = await make_question(pg, seed)
    q2 = await make_question(pg, seed, student_id=seed.other_student_id)
    a, _ = await ensure_flashcard_for_highlight(
        pg, highlight=await _highlight(pg, seed, q1.id), answer_text="A", answer_ok=True
    )
    b, created = await ensure_flashcard_for_highlight(
        pg,
        highlight=await _highlight(pg, seed, q2.id, student_id=seed.other_student_id),
        answer_text="B",
        answer_ok=True,
    )
    assert created is True and a.id != b.id
    assert b.student_user_id == seed.other_student_id


@requires_pg
async def test_unique_index_resolves_concurrent_duplicate(pg: AsyncSession) -> None:
    """A card inserted behind the service's back (the race winner) is reused."""
    seed = await seed_lecture(pg)
    q = await make_question(pg, seed)
    hl = await _highlight(pg, seed, q.id)
    winner = SchoolStudentFlashcard(
        student_user_id=seed.student_id,
        lecture_id=seed.lecture_id,
        front_text="mass",
        back_text="winner",
        dedupe_hash=flashcard_dedupe_hash(highlight_text="mass", lecture_id=seed.lecture_id),
    )
    pg.add(winner)
    await pg.flush()

    card, created = await ensure_flashcard_for_highlight(
        pg, highlight=hl, answer_text="loser", answer_ok=True
    )
    assert created is False and card.id == winner.id


@requires_pg
async def test_failed_answer_creates_placeholder_back(pg: AsyncSession) -> None:
    seed = await seed_lecture(pg)
    q = await make_question(pg, seed)
    card, created = await ensure_flashcard_for_highlight(
        pg,
        highlight=await _highlight(pg, seed, q.id),
        answer_text="I couldn't generate an answer right now.",
        answer_ok=False,
    )
    assert created is True and card.back_text == ""


@requires_pg
async def test_card_survives_highlight_deletion(pg: AsyncSession) -> None:
    seed = await seed_lecture(pg)
    q = await make_question(pg, seed)
    hl = await _highlight(pg, seed, q.id)
    card, _ = await ensure_flashcard_for_highlight(
        pg, highlight=hl, answer_text="A", answer_ok=True
    )
    await pg.commit()

    await pg.delete(hl)  # hard delete → FK SET NULL, card remains
    await pg.commit()
    survivor = await pg.get(SchoolStudentFlashcard, card.id, populate_existing=True)
    assert survivor is not None
    assert survivor.source_highlight_id is None
    assert survivor.front_text == "mass"


@requires_pg
async def test_soft_deleted_card_allows_a_fresh_one(pg: AsyncSession) -> None:
    seed = await seed_lecture(pg)
    q1 = await make_question(pg, seed)
    q2 = await make_question(pg, seed)
    first, _ = await ensure_flashcard_for_highlight(
        pg, highlight=await _highlight(pg, seed, q1.id), answer_text="A", answer_ok=True
    )
    first.deleted_at = now()
    await pg.flush()
    second, created = await ensure_flashcard_for_highlight(
        pg, highlight=await _highlight(pg, seed, q2.id), answer_text="B", answer_ok=True
    )
    assert created is True and second.id != first.id


@requires_pg
async def test_persist_answer_creates_card_for_highlight_question(pg: AsyncSession) -> None:
    """End-to-end through the answer pipeline's persist step."""
    from app.features.student_questions.answer_pipeline import _persist_answer

    seed = await seed_lecture(pg)
    q = await make_question(pg, seed)
    await _highlight(pg, seed, q.id)

    new_card = await _persist_answer(
        pg, question=q, answer_text="Mass is matter.", tags={}, next_turn_index=1
    )
    assert new_card is not None and new_card.back_text == "Mass is matter."
    assert q.answer_text == "Mass is matter."

    # A follow-up answer on the same thread must not create a second card.
    again = await _persist_answer(
        pg, question=q, answer_text="More detail.", tags={}, next_turn_index=3
    )
    assert again is None
    assert await _count_cards(pg, seed.student_id) == 1


@requires_pg
async def test_persist_answer_free_form_question_creates_no_card(pg: AsyncSession) -> None:
    from app.features.student_questions.answer_pipeline import _persist_answer

    seed = await seed_lecture(pg)
    q = await make_question(pg, seed, highlight_text=None)
    assert (
        await _persist_answer(pg, question=q, answer_text="x", tags={}, next_turn_index=1) is None
    )
    assert await _count_cards(pg, seed.student_id) == 0
