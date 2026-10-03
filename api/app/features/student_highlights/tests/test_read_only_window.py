"""flow-6 §5.10 — graduated students in the read-only window can't create highlights."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.features.lectures.models import SchoolLecture, SchoolLectureParagraph
from app.features.student_highlights.service import StudentHighlightService
from app.features.student_highlights.tests.pg_support import (
    make_question,
    requires_pg,
    seed_lecture,
)
from app.features.student_onboarding.models import StudentProfile


async def _persist(pg: AsyncSession, seed: object, question_id: str) -> object:
    lecture = await pg.get(SchoolLecture, seed.lecture_id)  # type: ignore[attr-defined]
    paragraph = await pg.get(SchoolLectureParagraph, seed.paragraph_id)  # type: ignore[attr-defined]
    return await StudentHighlightService(pg).persist_for_question(
        student_user_id=seed.student_id,  # type: ignore[attr-defined]
        lecture=lecture,  # type: ignore[arg-type]
        question_id=question_id,
        tenant_type="school",
        paragraph=paragraph,
        highlighted_text="mass",
        offset_hint=None,
        source_chunk_id=None,
    )


@requires_pg
async def test_graduated_student_in_read_only_window_creates_no_highlight(pg: AsyncSession) -> None:
    seed = await seed_lecture(pg)
    pg.add(
        StudentProfile(
            user_id=seed.student_id,
            display_name="Grad",
            language_preference="en",
            is_graduated=True,
            migrated_out=False,
        )
    )
    await pg.flush()
    q = await make_question(pg, seed)
    assert await _persist(pg, seed, q.id) is None


@requires_pg
async def test_regular_student_still_creates_highlight(pg: AsyncSession) -> None:
    seed = await seed_lecture(pg)
    pg.add(StudentProfile(user_id=seed.student_id, display_name="S", language_preference="en"))
    await pg.flush()
    q = await make_question(pg, seed)
    assert await _persist(pg, seed, q.id) is not None
