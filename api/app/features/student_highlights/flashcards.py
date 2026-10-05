"""Auto-flashcard generation — T-186 (flow-6 §3.6 / §5.5, #58).

Runs on every highlight + answer pair, inside the answer-persist transaction.
Only *creates* cards (and, T-187, reports which are new so the caller can
publish ``flashcard.created``). Scheduling / spaced repetition is Flow 8/9's
domain (py-fsrs, M-17/M-18) and deliberately absent here.
"""

from __future__ import annotations

import hashlib
import re

import structlog
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import not_deleted
from app.features.student_highlights.models import (
    FlashcardSourceType,
    SchoolStudentFlashcard,
    SchoolStudentHighlight,
)

logger = structlog.get_logger(__name__)

_WS = re.compile(r"\s+")


def normalise_highlight_text(text: str) -> str:
    """Whitespace-collapsed, case-folded form used only for dedupe hashing."""
    return _WS.sub(" ", text).strip().casefold()


def flashcard_dedupe_hash(*, highlight_text: str, lecture_id: str) -> str:
    """hash(highlight_text, lecture_id) per §3.6 (sha256 hex, 64 chars).

    The unit-separator keeps ``("ab", "c")`` and ``("a", "bc")`` distinct.
    """
    payload = f"{lecture_id}\x1f{normalise_highlight_text(highlight_text)}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


async def _find_live(
    session: AsyncSession, *, student_user_id: str, dedupe_hash: str
) -> SchoolStudentFlashcard | None:
    result = await session.execute(
        select(SchoolStudentFlashcard).where(
            SchoolStudentFlashcard.student_user_id == student_user_id,
            SchoolStudentFlashcard.dedupe_hash == dedupe_hash,
            not_deleted(SchoolStudentFlashcard),
        )
    )
    return result.scalars().first()


async def ensure_flashcard_for_highlight(
    session: AsyncSession,
    *,
    highlight: SchoolStudentHighlight,
    answer_text: str,
    answer_ok: bool,
) -> tuple[SchoolStudentFlashcard, bool]:
    """Create (or reuse) the student's flashcard for this highlight.

    Returns ``(card, created)``. ``created`` is False when a live card with the
    same dedupe hash already exists — a repeat highlight reuses it (§5.5) and
    must not emit a second ``flashcard.created``.

    ``answer_ok=False`` (LLM failure / empty answer) stores an empty back — the
    UI renders it as an editable placeholder (§5.5) rather than persisting the
    generic error sentence as card content. The caller owns the commit.
    """
    dedupe = flashcard_dedupe_hash(
        highlight_text=highlight.highlighted_text, lecture_id=highlight.lecture_id
    )
    existing = await _find_live(
        session, student_user_id=highlight.student_user_id, dedupe_hash=dedupe
    )
    if existing is not None:
        return existing, False

    card = SchoolStudentFlashcard(
        student_user_id=highlight.student_user_id,
        lecture_id=highlight.lecture_id,
        source_type=FlashcardSourceType.HIGHLIGHT,
        source_highlight_id=highlight.id,
        concept_tag=highlight.concept_tag,
        front_text=highlight.highlighted_text,
        back_text=answer_text if answer_ok else "",
        dedupe_hash=dedupe,
        tenant_type=highlight.tenant_type,
    )
    # SAVEPOINT: a concurrent answer for the same highlight text can win the
    # partial unique index; roll back only this insert and reuse the winner.
    try:
        async with session.begin_nested():
            session.add(card)
            await session.flush()
    except IntegrityError:
        winner = await _find_live(
            session, student_user_id=highlight.student_user_id, dedupe_hash=dedupe
        )
        if winner is None:
            raise
        logger.info("flashcard_dedupe_race_resolved", flashcard_id=winner.id)
        return winner, False
    return card, True
