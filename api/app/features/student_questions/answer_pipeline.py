"""T-158 AI answer pipeline — Pattern S RAG + ``lecture_qa_v1`` + token stream.

Flow:
1. Resolve lecture curriculum/reference corpus (wizard draft metadata, else
   school-scoped collections).
2. Dual-RAG retrieve (curriculum 1.5×), DB-chunk fallback when Qdrant empty.
3. Out-of-curriculum → Pattern A web primitives (``web_search`` / ``web_fetch``);
   when web also empty → ``no_coverage`` ([No Source] + [AI Knowledge]).
4. Prepend base §8.20 persona; fold T-161 exam overlay when the student has a
   framework selected.
5. Stream plain text tokens (wrapped as SSE by ``stream_response``); persist
   answer + source spans on ``SchoolStudentQuestion`` (+ assistant turn).
"""

from __future__ import annotations

from collections.abc import AsyncGenerator, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.lectures.exam_overlay import (
    ExamOverlayContext,
    get_student_exam_framework_overlay,
)
from app.features.lectures.generation import apply_curriculum_weight
from app.features.lectures.models import SchoolLecture, SchoolLectureDraft
from app.features.library.school_models import (
    LibraryContentType,
    SchoolLibraryItem,
    SchoolLibraryItemChunk,
)
from app.features.offerings.models import GradeSubjectOffering
from app.features.student_questions.models import (
    ConversationRole,
    SchoolStudentQuestion,
    SchoolStudentQuestionConversation,
)
from app.features.subjects.models import Subject
from app.infrastructure.llm.client import chat, stream_chat
from app.infrastructure.llm.persona import prepend_persona
from app.infrastructure.llm.persona import resolve_base_persona as resolve_base_persona
from app.infrastructure.llm.prompts.lecture_qa_v1 import (
    PROMPT_VERSION,
    LectureQaInput,
    QaChunkRef,
    render,
)
from app.infrastructure.rag.embedder import school_library_collection
from app.infrastructure.rag.retriever import retrieve
from app.infrastructure.rag.web_search import web_fetch, web_search

logger = structlog.get_logger(__name__)

CURRICULUM_WEIGHT = 1.5
_TOP_CURRICULUM = 8
_TOP_REFERENCE = 6
_TOP_WEB = 3

SourceTierName = Literal["curriculum", "reference", "ai_knowledge", "web", "no_source"]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _badge_for_tier(tier: SourceTierName, book_name: str | None = None) -> str:
    if tier == "curriculum":
        return "[Curriculum]"
    if tier == "reference":
        return f"[Ref: {book_name or 'Book'}]"
    if tier == "web":
        return "[Web]"
    if tier == "no_source":
        return "[No Source]"
    return "[AI Knowledge]"


def build_source_tags(
    *,
    curriculum: list[QaChunkRef],
    reference: list[QaChunkRef],
    web: list[QaChunkRef],
    no_coverage: bool,
) -> tuple[str, list[dict[str, Any]]]:
    """Compute primary badge + span dicts for ``answer_source_tags_jsonb``."""
    tags: list[dict[str, Any]] = []
    for chunk in curriculum:
        tags.append(
            {
                "badge": _badge_for_tier("curriculum"),
                "tier": "curriculum",
                "chunk_id": chunk.source_id or None,
                "book_name": chunk.source_label,
                "excerpt": chunk.text[:280],
                "source_url": None,
            }
        )
    for chunk in reference:
        tags.append(
            {
                "badge": _badge_for_tier("reference", chunk.source_label),
                "tier": "reference",
                "chunk_id": chunk.source_id or None,
                "book_name": chunk.source_label,
                "excerpt": chunk.text[:280],
                "source_url": None,
            }
        )
    for chunk in web:
        tags.append(
            {
                "badge": _badge_for_tier("web"),
                "tier": "web",
                "chunk_id": chunk.source_id or None,
                "book_name": chunk.source_label,
                "excerpt": chunk.text[:280],
                "source_url": chunk.source_id if chunk.source_id.startswith("http") else None,
            }
        )

    if curriculum:
        primary = _badge_for_tier("curriculum")
    elif reference:
        primary = tags[0]["badge"] if tags else _badge_for_tier("reference")
    elif web:
        primary = _badge_for_tier("web")
    elif no_coverage:
        # Pattern A attempted but returned nothing — badge [Web] with a clear stub
        # (T-158), plus [No Source] so the panel can show honest unavailability.
        primary = _badge_for_tier("web")
        tags.append(
            {
                "badge": primary,
                "tier": "web",
                "chunk_id": None,
                "book_name": None,
                "excerpt": (
                    "Web fallback unavailable — Pattern A search returned no usable sources."
                ),
                "source_url": None,
            }
        )
        tags.append(
            {
                "badge": _badge_for_tier("no_source"),
                "tier": "no_source",
                "chunk_id": None,
                "book_name": None,
                "excerpt": "No curriculum, reference, or web coverage found.",
                "source_url": None,
            }
        )
        tags.append(
            {
                "badge": _badge_for_tier("ai_knowledge"),
                "tier": "ai_knowledge",
                "chunk_id": None,
                "book_name": None,
                "excerpt": "Answer may use general teaching knowledge when sources are absent.",
                "source_url": None,
            }
        )
    else:
        primary = _badge_for_tier("ai_knowledge")
        tags.append(
            {
                "badge": primary,
                "tier": "ai_knowledge",
                "chunk_id": None,
                "book_name": None,
                "excerpt": "Answer draws on general teaching knowledge.",
                "source_url": None,
            }
        )

    return primary, tags


def source_tags_jsonb(primary_badge: str, spans: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "primary_badge": primary_badge,
        "badges": list(dict.fromkeys([primary_badge, *[str(s.get("badge")) for s in spans]])),
        "spans": spans,
        "prompt_version": PROMPT_VERSION,
    }


def _hit_text(hit: dict[str, Any]) -> str:
    raw_payload = hit.get("payload")
    payload: dict[str, Any] = raw_payload if isinstance(raw_payload, dict) else {}
    return str(payload.get("text") or payload.get("chunk_text") or "")


def _hit_label(hit: dict[str, Any]) -> str:
    raw_payload = hit.get("payload")
    payload: dict[str, Any] = raw_payload if isinstance(raw_payload, dict) else {}
    return str(payload.get("title") or "Source")


def _to_chunk(hit: dict[str, Any], tier: Literal["curriculum", "reference"]) -> QaChunkRef | None:
    text = _hit_text(hit)
    if not text.strip():
        return None
    return QaChunkRef(
        source_id=str(hit.get("id") or ""),
        source_label=_hit_label(hit),
        tier=tier,
        text=text[:4000],
    )


async def _load_db_chunks(
    session: AsyncSession, item_ids: list[str]
) -> list[SchoolLibraryItemChunk]:
    if not item_ids:
        return []
    result = await session.execute(
        select(SchoolLibraryItemChunk)
        .where(SchoolLibraryItemChunk.library_item_id.in_(item_ids))
        .order_by(
            SchoolLibraryItemChunk.library_item_id.asc(),
            SchoolLibraryItemChunk.chunk_index.asc(),
        )
    )
    return list(result.scalars().all())


async def _retrieve_for_items(
    *,
    query: str,
    school_id: str,
    items: list[SchoolLibraryItem],
    content_type: LibraryContentType,
    top_k: int,
) -> list[dict[str, Any]]:
    collection = school_library_collection(content_type.value)
    hits = await retrieve(
        query,
        collection,
        top_k=top_k,
        tenant_filter={"school_id": school_id},
    )
    if not items:
        return [dict(h) for h in hits]
    allowed = {item.id for item in items}
    filtered: list[dict[str, Any]] = []
    for hit in hits:
        raw_payload = hit.get("payload")
        payload: dict[str, Any] = raw_payload if isinstance(raw_payload, dict) else {}
        item_id = str(payload.get("library_item_id") or payload.get("item_id") or "")
        if item_id and item_id not in allowed:
            continue
        filtered.append(dict(hit))
    return filtered


def _extract_corpus_ids(draft: SchoolLectureDraft, lecture_id: str) -> tuple[str | None, list[str]]:
    if not isinstance(draft.wizard_state_jsonb, dict):
        return None, []
    data = draft.wizard_state_jsonb.get("data")
    if not isinstance(data, dict):
        return None, []
    if str(data.get("lecture_id") or "") != lecture_id:
        return None, []
    curriculum_id: str | None = None
    raw_c = data.get("curriculum_id")
    if isinstance(raw_c, str) and raw_c:
        curriculum_id = raw_c
    reference_ids: list[str] = []
    raw_refs = data.get("reference_book_ids")
    if isinstance(raw_refs, list):
        reference_ids = [str(r) for r in raw_refs if r]
    return curriculum_id, reference_ids


async def resolve_lecture_corpus(
    session: AsyncSession, lecture: SchoolLecture
) -> tuple[list[SchoolLibraryItem], list[SchoolLibraryItem]]:
    """Curriculum + reference library items for this lecture (best-effort)."""
    stmt = select(SchoolLectureDraft).order_by(SchoolLectureDraft.created_at.desc()).limit(50)
    if lecture.teacher_user_id:
        stmt = (
            select(SchoolLectureDraft)
            .where(SchoolLectureDraft.teacher_user_id == lecture.teacher_user_id)
            .order_by(SchoolLectureDraft.created_at.desc())
            .limit(50)
        )
    result = await session.execute(stmt)
    curriculum_id: str | None = None
    reference_ids: list[str] = []
    for draft in result.scalars().all():
        cid, refs = _extract_corpus_ids(draft, lecture.id)
        if cid or refs:
            curriculum_id, reference_ids = cid, refs
            break

    curriculum_items: list[SchoolLibraryItem] = []
    if curriculum_id:
        item = await session.get(SchoolLibraryItem, curriculum_id)
        if item is not None:
            curriculum_items.append(item)
    ref_items: list[SchoolLibraryItem] = []
    for rid in reference_ids:
        item = await session.get(SchoolLibraryItem, rid)
        if item is not None:
            ref_items.append(item)
    return curriculum_items, ref_items


async def _fetch_web_fallback_chunks(query: str) -> list[QaChunkRef]:
    """Pattern A web primitives (§7.12). Empty on any failure."""
    try:
        results = await web_search(query, max_results=_TOP_WEB)
    except (httpx.HTTPError, ValueError, OSError) as exc:
        logger.warning("lecture_qa_web_search_failed", query=query, error=str(exc))
        return []

    chunks: list[QaChunkRef] = []
    for hit in results[:_TOP_WEB]:
        text = await web_fetch(hit.url)
        if not text.strip():
            continue
        chunks.append(
            QaChunkRef(
                source_id=hit.url,
                source_label=hit.title or hit.url,
                tier="web",
                text=text[:4000],
            )
        )
    return chunks


async def retrieve_qa_chunks(
    session: AsyncSession,
    *,
    lecture: SchoolLecture,
    query: str,
) -> tuple[list[QaChunkRef], list[QaChunkRef], list[QaChunkRef], bool]:
    """Pattern S dual-RAG + web fallback. Returns ``(..., no_coverage)``."""
    school_id = lecture.school_id or ""
    curriculum_items, ref_items = await resolve_lecture_corpus(session, lecture)

    curriculum_q: list[dict[str, Any]] = []
    reference_q: list[dict[str, Any]] = []
    if school_id:
        curriculum_q = await _retrieve_for_items(
            query=query,
            school_id=school_id,
            items=curriculum_items,
            content_type=LibraryContentType.CURRICULUM,
            top_k=_TOP_CURRICULUM,
        )
        reference_q = await _retrieve_for_items(
            query=query,
            school_id=school_id,
            items=ref_items,
            content_type=LibraryContentType.REFERENCE,
            top_k=_TOP_REFERENCE,
        )

    if not curriculum_q and curriculum_items:
        db_chunks = await _load_db_chunks(session, [i.id for i in curriculum_items])
        title_by_id = {i.id: i.title for i in curriculum_items}
        curriculum_q = [
            {
                "id": c.id,
                "score": 1.0 / (1 + c.chunk_index),
                "payload": {
                    "library_item_id": c.library_item_id,
                    "text": c.chunk_text,
                    "title": title_by_id.get(c.library_item_id, "Curriculum"),
                },
            }
            for c in db_chunks[:_TOP_CURRICULUM]
        ]
    if not reference_q and ref_items:
        db_chunks = await _load_db_chunks(session, [i.id for i in ref_items])
        title_by_id = {i.id: i.title for i in ref_items}
        reference_q = [
            {
                "id": c.id,
                "score": 1.0 / (1 + c.chunk_index),
                "payload": {
                    "library_item_id": c.library_item_id,
                    "text": c.chunk_text,
                    "title": title_by_id.get(c.library_item_id, "Reference"),
                },
            }
            for c in db_chunks[:_TOP_REFERENCE]
        ]

    if school_id and not curriculum_q and not curriculum_items:
        curriculum_q = await _retrieve_for_items(
            query=query,
            school_id=school_id,
            items=[],
            content_type=LibraryContentType.CURRICULUM,
            top_k=_TOP_CURRICULUM,
        )
    if school_id and not reference_q and not ref_items:
        reference_q = await _retrieve_for_items(
            query=query,
            school_id=school_id,
            items=[],
            content_type=LibraryContentType.REFERENCE,
            top_k=_TOP_REFERENCE,
        )

    _ = apply_curriculum_weight(curriculum_q, reference_q, weight=CURRICULUM_WEIGHT)

    curr_refs: list[QaChunkRef] = []
    for hit in curriculum_q:
        chunk = _to_chunk(hit, "curriculum")
        if chunk is not None:
            curr_refs.append(chunk)

    ref_refs: list[QaChunkRef] = []
    for hit in reference_q:
        chunk = _to_chunk(hit, "reference")
        if chunk is not None:
            ref_refs.append(chunk)

    web_refs: list[QaChunkRef] = []
    no_coverage = False
    if not curr_refs and not ref_refs:
        web_refs = await _fetch_web_fallback_chunks(query)
        if web_refs:
            logger.info("lecture_qa_web_fallback", lecture_id=lecture.id, web_hits=len(web_refs))
        else:
            no_coverage = True
            logger.info("lecture_qa_no_coverage", lecture_id=lecture.id)

    return curr_refs, ref_refs, web_refs, no_coverage


async def _load_student_exam_overlay(
    session: AsyncSession, *, lecture: SchoolLecture, student_user_id: str
) -> ExamOverlayContext | None:
    if lecture.grade_subject_offering_id is None:
        return None
    offering = await session.get(GradeSubjectOffering, lecture.grade_subject_offering_id)
    if offering is None:
        return None
    subject = await session.get(Subject, offering.subject_id)
    if subject is None:
        return None
    return await get_student_exam_framework_overlay(
        session,
        student_user_id=student_user_id,
        grade_id=offering.grade_id,
        subject_name=subject.name,
    )


@dataclass
class _RenderedPrompt:
    system: str
    user: str
    temperature: float
    max_tokens: int


async def _render_qa_prompt(
    session: AsyncSession,
    *,
    question: SchoolStudentQuestion,
    lecture: SchoolLecture,
    turns: Sequence[SchoolStudentQuestionConversation],
    curr: list[QaChunkRef],
    refs: list[QaChunkRef],
    web: list[QaChunkRef],
    no_coverage: bool,
) -> tuple[_RenderedPrompt, str, list[dict[str, Any]]]:
    overlay = await _load_student_exam_overlay(
        session, lecture=lecture, student_user_id=question.student_user_id
    )
    lang = (
        question.question_language
        if question.question_language in ("en", "ur", "sd", "ps")
        else "en"
    )
    history: list[str] = []
    turns_list = list(turns)
    for i, turn in enumerate(turns_list):
        if i == len(turns_list) - 1 and turn.role == ConversationRole.USER:
            continue
        history.append(f"{turn.role.value}: {turn.content[:500]}")

    latest_user = question.question_text
    if turns_list:
        for turn in reversed(turns_list):
            if turn.role == ConversationRole.USER:
                latest_user = turn.content
                break

    inp = LectureQaInput(
        question_text=latest_user,
        highlight_text=question.highlight_text,
        lecture_topic=lecture.topic,
        target_language=lang,  # type: ignore[arg-type]
        curriculum_chunks=curr[:_TOP_CURRICULUM],
        reference_chunks=refs[:_TOP_REFERENCE],
        web_chunks=web[:_TOP_WEB],
        no_coverage=no_coverage,
        web_stub_notice=(
            "WEB FALLBACK UNAVAILABLE: curriculum and reference had no coverage, and "
            "web search returned nothing usable. Prefer [No Source] / honest refusal; "
            "do not invent facts."
            if no_coverage
            else None
        ),
        exam_framework_name=overlay.framework_name if overlay else None,
        exam_strategy_summary=overlay.exam_strategy_summary if overlay else None,
        exam_priority_topics=list(overlay.priority_topics) if overlay else [],
        conversation_history=history,
    )
    prompt = render(inp)
    persona = await resolve_base_persona(
        session, student_user_id=question.student_user_id, language=lang
    )
    primary, spans = build_source_tags(
        curriculum=curr[:_TOP_CURRICULUM],
        reference=refs[:_TOP_REFERENCE],
        web=web[:_TOP_WEB],
        no_coverage=no_coverage,
    )
    return (
        _RenderedPrompt(
            system=prepend_persona(persona, prompt.system),
            user=prompt.user,
            temperature=prompt.temperature,
            max_tokens=prompt.max_tokens,
        ),
        primary,
        spans,
    )


async def _persist_answer(
    session: AsyncSession,
    *,
    question: SchoolStudentQuestion,
    answer_text: str,
    tags: dict[str, Any],
    next_turn_index: int,
) -> None:
    question.answer_text = answer_text
    question.answer_source_tags_jsonb = tags
    question.answered_at = _utcnow()
    session.add(
        SchoolStudentQuestionConversation(
            root_question_id=question.id,
            turn_index=next_turn_index,
            role=ConversationRole.ASSISTANT,
            content=answer_text,
            source_tags_jsonb=tags,
        )
    )
    await session.flush()
    await session.commit()


async def stream_answer_for_question(
    session: AsyncSession,
    *,
    question: SchoolStudentQuestion,
    lecture: SchoolLecture,
    turns: Sequence[SchoolStudentQuestionConversation],
) -> AsyncGenerator[str, None]:
    """Yield plain answer tokens (SSE-wrapped by the router via ``stream_response``)."""
    # Replay stored answer without re-calling the LLM.
    if question.answer_text:
        yield question.answer_text
        return

    latest_user = question.question_text
    for turn in reversed(list(turns)):
        if turn.role == ConversationRole.USER:
            latest_user = turn.content
            break
    query = latest_user
    if question.highlight_text:
        query = f"{query}\n{question.highlight_text}"

    curr, refs, web, no_coverage = await retrieve_qa_chunks(
        session, lecture=lecture, query=query
    )
    prompt, primary, spans = await _render_qa_prompt(
        session,
        question=question,
        lecture=lecture,
        turns=turns,
        curr=curr,
        refs=refs,
        web=web,
        no_coverage=no_coverage,
    )
    tags = source_tags_jsonb(primary, spans)

    parts: list[str] = []
    try:
        async for token in stream_chat(
            [
                {"role": "system", "content": prompt.system},
                {"role": "user", "content": prompt.user},
            ],
            task="student_qa",
            temperature=prompt.temperature,
            max_tokens=prompt.max_tokens,
        ):
            parts.append(token)
            yield token
    except Exception as exc:
        logger.error("lecture_qa_stream_failed", question_id=question.id, error=str(exc))
        fallback = (
            "I couldn't generate an answer right now. Please try again in a moment. [No Source]"
        )
        parts = [fallback]
        yield fallback
        primary = "[No Source]"
        spans = [
            {
                "badge": "[No Source]",
                "tier": "no_source",
                "chunk_id": None,
                "book_name": None,
                "excerpt": "stream failed",
                "source_url": None,
            }
        ]
        tags = source_tags_jsonb(primary, spans)

    answer = "".join(parts).strip() or "I don't have information on this. [No Source]"
    next_idx = max((t.turn_index for t in turns), default=-1) + 1
    await _persist_answer(
        session,
        question=question,
        answer_text=answer,
        tags=tags,
        next_turn_index=next_idx,
    )
    logger.info(
        "lecture_qa_answer_stored",
        question_id=question.id,
        prompt_version=PROMPT_VERSION,
        primary_badge=primary,
    )


async def generate_and_store_answer(
    session: AsyncSession,
    *,
    question_id: str,
    root_question_id: str | None = None,
    turn_index: int | None = None,
) -> dict[str, Any]:
    """Non-streaming generation — used when a session is available at enqueue time."""
    qid = root_question_id or question_id
    question = await session.get(SchoolStudentQuestion, qid)
    if question is None:
        return {"answer_text": "", "primary_badge": "[No Source]"}
    lecture = await session.get(SchoolLecture, question.lecture_id)
    if lecture is None:
        return {"answer_text": "", "primary_badge": "[No Source]"}

    result = await session.execute(
        select(SchoolStudentQuestionConversation)
        .where(SchoolStudentQuestionConversation.root_question_id == question.id)
        .order_by(SchoolStudentQuestionConversation.turn_index.asc())
    )
    turns = list(result.scalars().all())

    latest_user = question.question_text
    for turn in reversed(turns):
        if turn.role == ConversationRole.USER:
            latest_user = turn.content
            break
    query = latest_user
    if question.highlight_text:
        query = f"{query}\n{question.highlight_text}"

    curr, refs, web, no_coverage = await retrieve_qa_chunks(
        session, lecture=lecture, query=query
    )
    prompt, primary, spans = await _render_qa_prompt(
        session,
        question=question,
        lecture=lecture,
        turns=turns,
        curr=curr,
        refs=refs,
        web=web,
        no_coverage=no_coverage,
    )
    tags = source_tags_jsonb(primary, spans)
    try:
        answer = await chat(
            [
                {"role": "system", "content": prompt.system},
                {"role": "user", "content": prompt.user},
            ],
            task="student_qa",
            temperature=prompt.temperature,
            max_tokens=prompt.max_tokens,
        )
    except Exception as exc:
        logger.error("lecture_qa_llm_failed", question_id=qid, error=str(exc))
        answer = (
            "I couldn't generate an answer right now. Please try again in a moment. [No Source]"
        )
        primary = "[No Source]"
        spans = [
            {
                "badge": "[No Source]",
                "tier": "no_source",
                "chunk_id": None,
                "book_name": None,
                "excerpt": "LLM call failed",
                "source_url": None,
            }
        ]
        tags = source_tags_jsonb(primary, spans)

    answer = (answer or "").strip() or "I don't have information on this. [No Source]"
    next_idx = max((t.turn_index for t in turns), default=-1) + 1
    await _persist_answer(
        session,
        question=question,
        answer_text=answer,
        tags=tags,
        next_turn_index=next_idx,
    )
    return {"answer_text": answer, "primary_badge": primary, "turn_index": turn_index}


async def enqueue_answer_generation(
    *,
    question_id: str,
    root_question_id: str | None = None,
    turn_index: int | None = None,
    session: AsyncSession | None = None,
) -> None:
    """Hook after ask / follow-up.

    When ``session`` is provided, runs sync generation + persist. Otherwise the
    client is expected to open the SSE stream endpoint (service default path).
    """
    if session is None:
        logger.debug(
            "student_question_answer_pipeline_awaiting_stream",
            question_id=question_id,
            root_question_id=root_question_id,
            turn_index=turn_index,
            ticket="T-158",
        )
        return
    await generate_and_store_answer(
        session,
        question_id=question_id,
        root_question_id=root_question_id,
        turn_index=turn_index,
    )
