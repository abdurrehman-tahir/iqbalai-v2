"""T-194 — M-15 milestone E2E: the full Flow 6 (§3.6 / §3.10 / §3.11) journey.

Real services against real Postgres (DB_URL, as CI provides); only the
external boundaries are mocked — the LLM (answer + enrichment), RAG retrieval,
Celery enqueue, and the NATS publisher (captured to assert the event). No live
network. Mirrors the M-10 chained-flow test style (test_m10_e2e_flow.py).

Journey (numbers match the milestone acceptance list):
 1-4  student opens the lecture, highlights, asks, gets an answer → highlight persisted
 5-7  flashcard created; duplicate highlight → no second card; event emitted once
 8-12 return → yellow mark restored; lecture re-edited → mark drops silently, card survives
13-15 My Highlights: both highlights, lecture + concept tags, paired flashcard
16-20 concept reached → cache miss → generated + persisted; 2nd student → cache hit, no regen
21-24 mini-sim renders (spec), state saved, restored on return
25-32 ratings: 1-5, blended 5% into the M-10 score, anonymous aggregate, no ranking
33    permission boundaries (other student / staff) hold throughout
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.concept_enrichment import service as enrichment_service_mod
from app.features.concept_enrichment.generation import generate_enrichment
from app.features.concept_enrichment.models import Career, SchoolConceptApplication
from app.features.concept_enrichment.service import ConceptEnrichmentService
from app.features.concept_enrichment.simulation import SimulationProgressService
from app.features.lecture_ratings.service import LectureRatingService
from app.features.lectures import events as lecture_events
from app.features.lectures.models import SchoolLecture, SchoolLectureParagraph, SchoolLectureVersion
from app.features.lectures.service import LectureService
from app.features.student_highlights.models import SchoolStudentFlashcard
from app.features.student_highlights.my_highlights import MyHighlightsService
from app.features.student_highlights.service import StudentHighlightService
from app.features.student_highlights.tests.pg_support import make_user, requires_pg, seed_lecture
from app.features.student_questions import answer_pipeline
from app.features.student_questions import service as question_service_mod
from app.features.student_questions.answer_pipeline import (
    _RenderedPrompt,
    generate_and_store_answer,
)
from app.features.student_questions.schemas import StudentQuestionCreateRequest
from app.features.student_questions.service import StudentQuestionService
from app.features.users.models import User, UserRole
from app.infrastructure.llm import client as llm_client
from app.infrastructure.llm.client import ChatUsage

pytestmark = requires_pg

PARAGRAPH = "Force equals mass times acceleration. Newton's second law links them."
ANSWER = "Mass is the amount of matter in an object; more mass needs more force."


async def _claims(pg: AsyncSession, user_id: str) -> dict[str, object]:
    user = await pg.get(User, user_id)
    assert user is not None
    return {"sub": user.authentik_id, "role": user.role.value, "user_id": user.id}


@pytest.fixture
def boundaries(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Mock ONLY external boundaries; everything else is the real code path."""
    published: list[tuple[str, dict[str, Any]]] = []

    async def _publish(subject: str, _event_type: str, payload: dict[str, Any], **_: Any) -> None:
        published.append((subject, payload))

    monkeypatch.setattr(lecture_events, "publish", _publish)  # NATS
    # Enrollment/GSO is M-03/M-12 territory — grant access so the flow exercises M-15.
    monkeypatch.setattr(LectureService, "student_can_access_lecture", AsyncMock(return_value=True))
    # Answer pipeline: RAG retrieval + prompt context + LLM.
    monkeypatch.setattr(question_service_mod, "enqueue_answer_generation", AsyncMock())
    monkeypatch.setattr(
        answer_pipeline, "retrieve_qa_chunks", AsyncMock(return_value=([], [], [], True))
    )
    monkeypatch.setattr(
        answer_pipeline,
        "_render_qa_prompt",
        AsyncMock(
            return_value=(
                _RenderedPrompt(system="s", user="u", temperature=0.2, max_tokens=200),
                "[AI Knowledge]",
                [],
            )
        ),
    )
    answer_llm = AsyncMock(return_value=ANSWER)
    monkeypatch.setattr(answer_pipeline, "chat", answer_llm)
    # Enrichment: Celery enqueue captured; LLM returns vocabulary-bound careers.
    enqueued: list[str] = []
    monkeypatch.setattr(enrichment_service_mod, "enqueue_enrichment", enqueued.append)
    return {"published": published, "answer_llm": answer_llm, "enqueued": enqueued}


async def _ask(pg: AsyncSession, claims: dict[str, object], seed: Any, session_id: str) -> str:
    question = await StudentQuestionService(pg).ask_question(
        claims,
        lecture_id=seed.lecture_id,
        session_id=session_id,
        payload=StudentQuestionCreateRequest(
            question_text="Explain: mass",
            highlight_text="mass",
            highlight_offset=PARAGRAPH.index("mass"),
            paragraph_id=seed.paragraph_id,
        ),
    )
    await generate_and_store_answer(pg, question_id=question.id)
    return question.id


async def test_m15_full_flow(
    pg: AsyncSession, boundaries: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    seed = await seed_lecture(pg, PARAGRAPH)
    me = await _claims(pg, seed.student_id)
    other = await _claims(pg, seed.other_student_id)

    # 1-4 — highlight + ask + answer → highlight persisted with anchor + ai_response_ref
    q1 = await _ask(pg, me, seed, seed.session_id)
    marks = await StudentHighlightService(pg).list_for_lecture(me, seed.lecture_id)
    assert len(marks) == 1
    assert marks[0].highlighted_text == "mass" and marks[0].question_id == q1
    assert marks[0].mark is not None and marks[0].mark.offset == PARAGRAPH.index("mass")

    # 5 — flashcard: front = highlight, back = AI answer, tagged lecture + concept
    cards = (
        (
            await pg.execute(
                select(SchoolStudentFlashcard).where(
                    SchoolStudentFlashcard.student_user_id == seed.student_id
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(cards) == 1
    card = cards[0]
    assert (card.front_text, card.back_text) == ("mass", ANSWER)
    assert card.lecture_id == seed.lecture_id and card.concept_tag == "Forces"

    # 7 — student.flashcard.created emitted once, tenant-tagged, refs only
    events = [p for s, p in boundaries["published"] if s == "student.flashcard.created"]
    assert len(events) == 1
    assert events[0]["flashcard_id"] == card.id
    assert events[0]["student_user_id"] == seed.student_id
    assert events[0]["concept_tag"] == "Forces"
    assert events[0]["school_id"] == seed.school_id and events[0]["tenant_type"] == "school"
    assert "back_text" not in events[0]

    # 6 — same text highlighted again → highlight stored, NO new card, NO new event
    await _ask(pg, me, seed, seed.session_id)
    assert (
        await pg.execute(
            select(func.count())
            .select_from(SchoolStudentFlashcard)
            .where(SchoolStudentFlashcard.student_user_id == seed.student_id)
        )
    ).scalar_one() == 1
    assert len([1 for s, _ in boundaries["published"] if s == "student.flashcard.created"]) == 1

    # 8-9 — returning to the lecture restores the yellow marks
    assert all(
        h.mark is not None
        for h in await StudentHighlightService(pg).list_for_lecture(me, seed.lecture_id)
    )
    # 33 — another student never sees them
    assert await StudentHighlightService(pg).list_for_lecture(other, seed.lecture_id) == []

    # 10-12 — teacher re-edits: the span is gone → marks drop silently, card survives
    lecture = await pg.get(SchoolLecture, seed.lecture_id)
    assert lecture is not None
    v2 = SchoolLectureVersion(lecture_id=lecture.id, version=2, body="edited")
    pg.add(v2)
    await pg.flush()
    pg.add(
        SchoolLectureParagraph(
            lecture_version_id=v2.id,
            ordinal=0,
            text="Force is a push or a pull acting on an object.",
            source_metadata_jsonb={"tier": "curriculum"},
        )
    )
    lecture.current_version_id = v2.id
    await pg.commit()
    after_edit = await StudentHighlightService(pg).list_for_lecture(me, seed.lecture_id)
    assert len(after_edit) == 2 and all(h.mark is None for h in after_edit)
    assert await pg.get(SchoolStudentFlashcard, card.id) is not None

    # 13-15 — My Highlights: chronological, lecture + concept tags, paired card
    items, total = await MyHighlightsService(pg).list_mine(me, page=1, page_size=20)
    assert total == 2
    assert items[0].created_at >= items[1].created_at
    for item in items:
        assert item.lecture.title == "Newton" and item.concept_tag == "Forces"
        assert item.flashcard is not None and item.flashcard.id == card.id
        assert item.flashcard.back_text == ANSWER

    # 16-18 — student reaches the concept → cache miss → generation (LLM mocked) → persisted
    concepts = await ConceptEnrichmentService(pg).list_lecture_concepts(me, seed.lecture_id)
    concept_id = concepts[0].concept_id
    first = await ConceptEnrichmentService(pg).get_enrichment(
        me, lecture_id=seed.lecture_id, concept_id=concept_id
    )
    assert first.status == "pending" and len(boundaries["enqueued"]) == 1
    careers = list(
        (await pg.execute(select(Career).order_by(Career.slug).limit(2))).scalars().all()
    )
    enrichment_llm = AsyncMock(
        return_value=ChatUsage(
            text=json.dumps(
                {
                    "real_world_uses": [
                        {"title": "Rickshaws", "description": "Heavier loads need more force."},
                        {"title": "Cricket", "description": "Bats change the ball's momentum."},
                    ],
                    "career_ids": [careers[0].id, "invented-career"],
                    "mini_sim": {
                        "title": "Push the cart",
                        "scenario": "A cart on a road in Lahore.",
                        "variables": [
                            {
                                "key": "mass",
                                "label": "Mass",
                                "unit": "kg",
                                "min": 1,
                                "max": 100,
                                "step": 1,
                                "default": 10,
                            },
                            {
                                "key": "accel",
                                "label": "Acceleration",
                                "unit": "m/s²",
                                "min": 0,
                                "max": 10,
                                "step": 1,
                                "default": 2,
                            },
                        ],
                        "output": {"label": "Force", "unit": "N", "expression": "mass * accel"},
                    },
                }
            ),
            prompt_tokens=800,
            completion_tokens=400,
        )
    )
    monkeypatch.setattr(llm_client, "chat_with_usage", enrichment_llm)
    assert await generate_enrichment(pg, boundaries["enqueued"][0]) == "ready"
    row = (
        await pg.execute(
            select(SchoolConceptApplication).where(
                SchoolConceptApplication.concept_id == concept_id
            )
        )
    ).scalar_one()
    assert row.career_link_ids == [careers[0].id]  # vocabulary only
    assert row.regen_cost_usd is not None

    # 19-20 — second student reaches the same concept → cached, no regeneration
    second = await ConceptEnrichmentService(pg).get_enrichment(
        other, lecture_id=seed.lecture_id, concept_id=concept_id
    )
    assert second.status == "ready" and second.careers[0].id == careers[0].id
    enrichment_llm.assert_awaited_once()
    assert len(boundaries["enqueued"]) == 1

    # 21-24 — mini-sim renders (spec), state saved, resumes on return; per student
    assert second.mini_sim is not None and second.mini_sim.output.expression == "mass * accel"
    await SimulationProgressService(pg).save(
        me, lecture_id=seed.lecture_id, concept_id=concept_id, values={"mass": 40, "accel": 3}
    )
    resumed = await SimulationProgressService(pg).get(
        me, lecture_id=seed.lecture_id, concept_id=concept_id
    )
    assert resumed.values == {"mass": 40.0, "accel": 3.0}
    assert (
        await SimulationProgressService(pg).get(
            other, lecture_id=seed.lecture_id, concept_id=concept_id
        )
    ).values == {}

    # 25-29 — optional 1-5 ratings; 5% weight into the M-10 AI score (95%)
    v2.scores_jsonb = {"total": 44}  # 80% AI
    await pg.flush()
    await LectureRatingService(pg).submit(me, seed.lecture_id, 5)
    await LectureRatingService(pg).submit(other, seed.lecture_id, 5)
    third = await make_user(pg, role=UserRole.STUDENT, school_id=seed.school_id)
    await LectureRatingService(pg).submit(await _claims(pg, third.id), seed.lecture_id, 5)

    # 30-31 — teacher: aggregate only (anonymous), blended score
    teacher = await _claims(pg, seed.teacher_id)
    summary = await LectureRatingService(pg).summary(teacher, seed.lecture_id)
    assert summary.rating_count == 3 and summary.average_rating == 5.0
    assert summary.ai_score == 44 and summary.quality_score == 81.0  # 0.95·80 + 0.05·100
    assert "student_user_id" not in summary.model_dump()

    # 32 — students only ever see their own rating; nothing ranks students by it
    assert (await LectureRatingService(pg).get_mine(other, seed.lecture_id)).rating == 5
    mine = await LectureRatingService(pg).get_mine(me, seed.lecture_id)
    assert set(mine.model_dump()) == {"lecture_id", "rating"}

    # 33 — a student can't read the staff aggregates
    from app.core.exceptions import PermissionDeniedError

    with pytest.raises(PermissionDeniedError):
        await LectureRatingService(pg).summary(me, seed.lecture_id)
    with pytest.raises(PermissionDeniedError):
        await MyHighlightsService(pg).lecture_aggregate(me, lecture_id=seed.lecture_id)
