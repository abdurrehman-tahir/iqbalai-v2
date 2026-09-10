"""Pattern S dual-RAG lecture generation pipeline — T-116.

Retrieves curriculum + reference chunks, weights curriculum 1.5×, synthesizes via
``lecture_generate_v1``, persists lecture_versions + lecture_paragraphs, emits NATS.

T-119 (#27) adds the 3-tier out-of-curriculum fallback: when curriculum AND
reference retrieval both come back empty for the topic, escalate to a SearXNG
web search before falling back to an honest "no information" paragraph.

T-120 adds the exam-framework overlay (Flow 4 v3 §3.5.4): additive exam-
readiness context surfaced when a PUBLISHED framework is relevant.
"""

from __future__ import annotations

import json
import re
from typing import Any, cast

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.audit.actions import LECTURE_GENERATED
from app.features.grades.models import Grade
from app.features.lectures.events import (
    LECTURE_GENERATION_REQUESTED,
    LECTURE_VERSION_CREATED,
    publish_lecture_event,
)
from app.features.lectures.exam_overlay import ExamOverlayContext, get_exam_framework_overlay
from app.features.lectures.generation_stream import append_token, mark_complete
from app.features.lectures.lecture_notifications import notify_generation_complete
from app.features.lectures.models import (
    LectureStatus,
    SchoolLecture,
    SchoolLectureParagraph,
    SchoolLectureVersion,
)
from app.features.lectures.schemas import (
    ParagraphSourceMetadata,
    SourceTier,
    TeacherTips,
    TeacherTipsRealWorldExample,
)
from app.features.library.school_models import (
    LibraryContentType,
    SchoolLibraryItem,
    SchoolLibraryItemChunk,
)
from app.features.offerings.models import GradeSubjectOffering
from app.features.subjects.models import Subject
from app.infrastructure.audit.log import audit
from app.infrastructure.llm.client import chat, stream_chat
from app.infrastructure.llm.prompts.lecture_generate_v1 import (
    PROMPT_VERSION,
    ChunkRef,
    LectureGenerateInput,
    LectureGenerateOutput,
    LectureParagraphOut,
    render,
)
from app.infrastructure.llm.prompts.lecture_teacher_tips_v1 import (
    PROMPT_VERSION as TEACHER_TIPS_PROMPT_VERSION,
)
from app.infrastructure.llm.prompts.lecture_teacher_tips_v1 import (
    LectureTeacherTipsInput,
    LectureTeacherTipsOutput,
)
from app.infrastructure.llm.prompts.lecture_teacher_tips_v1 import render as render_teacher_tips
from app.infrastructure.rag.embedder import school_library_collection
from app.infrastructure.rag.retriever import retrieve
from app.infrastructure.rag.web_search import web_fetch, web_search

logger = structlog.get_logger(__name__)

CURRICULUM_WEIGHT = 1.5
_TOP_CURRICULUM = 12
_TOP_REFERENCE = 8
_TOP_WEB = 5
_JSON_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def _hit_score(hit: dict[str, Any]) -> float:
    raw = hit.get("score", 0.0)
    if isinstance(raw, (int, float)):
        return float(raw)
    if isinstance(raw, str):
        try:
            return float(raw)
        except ValueError:
            return 0.0
    return 0.0


def apply_curriculum_weight(
    curriculum_hits: list[dict[str, Any]],
    reference_hits: list[dict[str, Any]],
    *,
    weight: float = CURRICULUM_WEIGHT,
) -> list[dict[str, Any]]:
    """Merge dual-RAG hits with curriculum scores multiplied by ``weight`` (1.5×)."""
    weighted: list[dict[str, Any]] = []
    for hit in curriculum_hits:
        row = dict(hit)
        row["score"] = _hit_score(row) * weight
        row["tier"] = "curriculum"
        weighted.append(row)
    for hit in reference_hits:
        row = dict(hit)
        row["tier"] = "reference"
        row["score"] = _hit_score(row)
        weighted.append(row)
    return sorted(weighted, key=_hit_score, reverse=True)


def _parse_json_payload(raw: str) -> dict[str, Any]:
    text = _JSON_FENCE_RE.sub("", raw.strip()).strip()
    return cast(dict[str, Any], json.loads(text))


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
    if not items:
        return []
    collection = school_library_collection(content_type.value)
    hits = await retrieve(
        query,
        collection,
        top_k=top_k,
        tenant_filter={"school_id": school_id},
    )
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


async def _fetch_web_fallback_chunks(topic: str) -> list[ChunkRef]:
    """Tier 3 (#27): SearXNG web search + fetch. Empty on any failure.

    A SearXNG outage must not fail lecture generation — it just means tier 3
    also comes up empty, cascading to tier 4 (the honest "no coverage" notice).
    """
    try:
        results = await web_search(topic, max_results=_TOP_WEB)
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("lecture_web_search_failed", topic=topic, error=str(exc))
        return []

    chunks: list[ChunkRef] = []
    for hit in results[:_TOP_WEB]:
        text = await web_fetch(hit.url)
        if not text.strip():
            continue
        chunks.append(
            ChunkRef(
                source_id=hit.url,
                source_label=hit.title or hit.url,
                tier="web",
                text=text[:4000],
            )
        )
    return chunks


async def _load_exam_overlay(
    session: AsyncSession, lecture: SchoolLecture
) -> ExamOverlayContext | None:
    """T-120: resolve the lecture's Grade + Subject, then look up the overlay.

    ``None`` (no offering, no subject row, or no relevant framework) means
    "no overlay" — the caller must not fail generation over this.
    """
    if lecture.grade_subject_offering_id is None:
        return None
    offering = await session.get(GradeSubjectOffering, lecture.grade_subject_offering_id)
    if offering is None:
        return None
    subject = await session.get(Subject, offering.subject_id)
    if subject is None:
        return None
    return await get_exam_framework_overlay(
        session, grade_id=offering.grade_id, subject_name=subject.name
    )


async def _load_grade_subject_context(
    session: AsyncSession, lecture: SchoolLecture
) -> tuple[str, int] | None:
    """Resolve (subject_name, grade_level_ordinal) for T-124's teacher-tips prompt.

    ``None`` means the lecture has no offering/subject/grade to describe —
    the caller must not fail generation over this (mirrors ``_load_exam_overlay``).
    """
    if lecture.grade_subject_offering_id is None:
        return None
    offering = await session.get(GradeSubjectOffering, lecture.grade_subject_offering_id)
    if offering is None:
        return None
    subject = await session.get(Subject, offering.subject_id)
    grade = await session.get(Grade, offering.grade_id)
    if subject is None or grade is None:
        return None
    return subject.name, grade.level_ordinal


async def run_teacher_tips_generation(
    session: AsyncSession,
    *,
    lecture_id: str,
    school_id: str,
    version_id: str,
    topic: str,
    target_language: str = "en",
) -> None:
    """Second, separate LLM call (T-124, #28, #41): teacher-facing delivery tips.

    General-knowledge-only — deliberately does NOT use curriculum/reference RAG
    chunks (the opposite grounding direction from ``run_lecture_generation``).
    Supplementary content: any failure here is logged and swallowed, never
    raised — the lecture itself already succeeded and must not be affected.
    """
    lecture = await session.get(SchoolLecture, lecture_id)
    if lecture is None or lecture.school_id != school_id:
        logger.warning("lecture_teacher_tips_lecture_not_found", lecture_id=lecture_id)
        return
    version = await session.get(SchoolLectureVersion, version_id)
    if version is None or version.lecture_id != lecture_id:
        logger.warning("lecture_teacher_tips_version_not_found", lecture_id=lecture_id)
        return

    context = await _load_grade_subject_context(session, lecture)
    if context is None:
        logger.warning("lecture_teacher_tips_no_grade_subject", lecture_id=lecture_id)
        return
    subject_name, grade_level_ordinal = context
    lang = target_language if target_language in ("en", "ur", "sd", "ps") else "en"

    prompt = render_teacher_tips(
        LectureTeacherTipsInput(
            topic=topic,
            subject_name=subject_name,
            grade_level_ordinal=grade_level_ordinal,
            target_language=lang,  # type: ignore[arg-type]
        )
    )
    try:
        raw = await chat(
            [
                {"role": "system", "content": prompt.system},
                {"role": "user", "content": prompt.user},
            ],
            task="lecture_teacher_tips",
            temperature=prompt.temperature,
            max_tokens=prompt.max_tokens,
        )
        parsed = LectureTeacherTipsOutput.model_validate(_parse_json_payload(raw))
    except Exception as exc:
        logger.warning(
            "lecture_teacher_tips_generation_failed",
            lecture_id=lecture_id,
            version_id=version_id,
            error=str(exc),
            prompt_version=TEACHER_TIPS_PROMPT_VERSION,
        )
        return

    tips = TeacherTips(
        delivery_tips=parsed.delivery_tips,
        technique_demo=parsed.technique_demo,
        real_world_examples=[
            TeacherTipsRealWorldExample(title=ex.title, text=ex.text)
            for ex in parsed.real_world_examples
        ],
        language=lang,
    )
    version.teacher_tips_jsonb = tips.to_jsonb()
    await session.commit()
    logger.info(
        "lecture_teacher_tips_persisted",
        lecture_id=lecture_id,
        version_id=version_id,
        prompt_version=TEACHER_TIPS_PROMPT_VERSION,
    )


async def run_lecture_generation(
    session: AsyncSession,
    *,
    lecture_id: str,
    school_id: str,
    topic: str,
    curriculum_id: str,
    reference_book_ids: list[str],
    teaching_mode: str,
    teacher_user_id: str,
    target_language: str = "en",
) -> str:
    """Execute Pattern S dual-RAG generation and persist v1. Returns version id."""
    lecture = await session.get(SchoolLecture, lecture_id)
    if lecture is None or lecture.school_id != school_id:
        raise ValueError(f"lecture not found: {lecture_id}")

    await publish_lecture_event(
        event_type=LECTURE_GENERATION_REQUESTED,
        payload={
            "lecture_id": lecture_id,
            "school_id": school_id,
            "teacher_user_id": teacher_user_id,
            "tenant_type": "school",
            "topic": topic,
        },
    )

    curriculum_item = await session.get(SchoolLibraryItem, curriculum_id)
    ref_items: list[SchoolLibraryItem] = []
    for rid in reference_book_ids:
        item = await session.get(SchoolLibraryItem, rid)
        if item is not None:
            ref_items.append(item)

    curriculum_q = await _retrieve_for_items(
        query=topic,
        school_id=school_id,
        items=[curriculum_item] if curriculum_item else [],
        content_type=LibraryContentType.CURRICULUM,
        top_k=_TOP_CURRICULUM,
    )
    reference_q = await _retrieve_for_items(
        query=topic,
        school_id=school_id,
        items=ref_items,
        content_type=LibraryContentType.REFERENCE,
        top_k=_TOP_REFERENCE,
    )

    # DB chunk fallback when Qdrant is empty (local/CI without vectors).
    if not curriculum_q and curriculum_item is not None:
        db_chunks = await _load_db_chunks(session, [curriculum_id])
        curriculum_q = [
            {
                "id": c.id,
                "score": 1.0 / (1 + c.chunk_index),
                "payload": {
                    "library_item_id": c.library_item_id,
                    "text": c.chunk_text,
                    "title": curriculum_item.title,
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

    # Weighted merge proves curriculum 1.5× scoring (acceptance #2); prompt uses
    # curriculum in retrieval order (structure) and references by weighted depth.
    merged = apply_curriculum_weight(curriculum_q, reference_q)
    logger.info(
        "lecture_dual_rag_retrieved",
        lecture_id=lecture_id,
        curriculum_hits=len(curriculum_q),
        reference_hits=len(reference_q),
        merged=len(merged),
        prompt_version=PROMPT_VERSION,
    )

    def _to_chunk(hit: dict[str, Any], tier: str) -> ChunkRef | None:
        raw_payload = hit.get("payload")
        payload: dict[str, Any] = raw_payload if isinstance(raw_payload, dict) else {}
        text = str(payload.get("text") or payload.get("chunk_text") or "")
        if not text.strip():
            return None
        return ChunkRef(
            source_id=str(hit.get("id") or ""),
            source_label=str(payload.get("title") or "Source"),
            tier="curriculum" if tier == "curriculum" else "reference",
            text=text[:4000],
        )

    curr_refs: list[ChunkRef] = []
    for hit in curriculum_q:
        chunk = _to_chunk(hit, "curriculum")
        if chunk is not None:
            curr_refs.append(chunk)

    ref_by_score = [h for h in merged if str(h.get("tier")) == "reference"]
    ref_refs: list[ChunkRef] = []
    for hit in ref_by_score:
        chunk = _to_chunk(hit, "reference")
        if chunk is not None:
            ref_refs.append(chunk)

    # T-119 (#27): tier 1 (curriculum) and tier 2 (reference) both came back
    # empty for this topic — escalate to tier 3 (SearXNG web search) before
    # falling back to the honest "no information" tier 4.
    web_refs: list[ChunkRef] = []
    no_coverage = False
    if not curr_refs and not ref_refs:
        web_refs = await _fetch_web_fallback_chunks(topic)
        no_coverage = not web_refs
        logger.info(
            "lecture_fallback_tier_used",
            lecture_id=lecture_id,
            tier="web" if web_refs else "no_coverage",
            web_hits=len(web_refs),
        )

    # T-120 (Flow 4 v3 §3.5.4): additive exam-readiness context — never
    # injected for Custom Persona (that's per-student, not class-wide; §3.2).
    exam_overlay = await _load_exam_overlay(session, lecture)
    if exam_overlay is not None:
        logger.info(
            "lecture_exam_overlay_applied",
            lecture_id=lecture_id,
            framework_name=exam_overlay.framework_name,
        )

    lang = target_language if target_language in ("en", "ur", "sd", "ps") else "en"
    mode = teaching_mode if teaching_mode in ("auto", "manual", "voice_assisted") else "auto"
    prompt = render(
        LectureGenerateInput(
            topic=topic,
            teaching_mode=mode,  # type: ignore[arg-type]
            target_language=lang,  # type: ignore[arg-type]
            curriculum_chunks=curr_refs[:_TOP_CURRICULUM],
            reference_chunks=ref_refs[:_TOP_REFERENCE],
            web_chunks=web_refs[:_TOP_WEB],
            no_coverage=no_coverage,
            exam_framework_name=exam_overlay.framework_name if exam_overlay else None,
            exam_strategy_summary=exam_overlay.exam_strategy_summary if exam_overlay else None,
            exam_priority_topics=exam_overlay.priority_topics if exam_overlay else [],
        )
    )
    # T-117: relay raw deltas token-by-token so a connected teacher sees live
    # progress (ws:lecture:<lecture_id>); the accumulated raw text below is
    # still parsed as one JSON payload once the stream ends, same as before.
    chunks: list[str] = []
    async for delta in stream_chat(
        [
            {"role": "system", "content": prompt.system},
            {"role": "user", "content": prompt.user},
        ],
        task="lecture_generate",
        temperature=prompt.temperature,
        max_tokens=prompt.max_tokens,
    ):
        chunks.append(delta)
        await append_token(lecture_id, delta)
    raw = "".join(chunks)
    try:
        parsed = LectureGenerateOutput.model_validate(_parse_json_payload(raw))
    except Exception:
        # Honest fallback: single ai_knowledge paragraph so the lecture still lands.
        logger.warning("lecture_generate_parse_failed", lecture_id=lecture_id)
        parsed = LectureGenerateOutput(
            title=topic[:500],
            paragraphs=[
                LectureParagraphOut(
                    text=raw.strip()[:8000] or f"Lecture draft on {topic}.",
                    tier="ai_knowledge",
                )
            ],
        )

    body = "\n\n".join(p.text for p in parsed.paragraphs)
    version = SchoolLectureVersion(
        lecture_id=lecture.id,
        version=1,
        body=body,
        scores_jsonb=None,
    )
    session.add(version)
    await session.flush()

    for ordinal, para in enumerate(parsed.paragraphs):
        tier = SourceTier(para.tier)
        meta = ParagraphSourceMetadata(
            tier=tier,
            book_name=para.book_name,
            chunk_id=para.chunk_id,
        )
        session.add(
            SchoolLectureParagraph(
                lecture_version_id=version.id,
                ordinal=ordinal,
                text=para.text,
                source_metadata_jsonb=meta.to_jsonb(),
            )
        )

    lecture.current_version_id = version.id
    lecture.title = parsed.title[:500]
    lecture.status = LectureStatus.GENERATED_V1
    await session.commit()

    await publish_lecture_event(
        event_type=LECTURE_VERSION_CREATED,
        payload={
            "lecture_id": lecture_id,
            "version_id": version.id,
            "version": 1,
            "school_id": school_id,
            "teacher_user_id": teacher_user_id,
            "tenant_type": "school",
        },
    )
    logger.info(
        "lecture_generation_persisted",
        lecture_id=lecture_id,
        version_id=version.id,
        paragraph_count=len(parsed.paragraphs),
    )

    # T-117 acceptance: stream completes → READY_FOR_EDIT. Auto-quiz generation
    # (flow-5 §3.2's gate between GENERATED_V1 and READY_FOR_EDIT/PUBLISH) isn't
    # built in M-09, so the transition is immediate here.
    lecture.status = LectureStatus.READY_FOR_EDIT
    await session.commit()

    # T-126: audit is synchronous and NOT best-effort (§14.10 — "if audit fails,
    # the action fails"); the notification below is best-effort (see its module
    # docstring) so a notify hiccup can't undo an already-successful generation.
    await audit(
        session=session,
        action=LECTURE_GENERATED,
        actor_id=teacher_user_id,
        actor_role="teacher",
        target_type="lecture",
        target_id=lecture_id,
        school_id=school_id,
        metadata={"version_id": version.id},
    )
    await notify_generation_complete(session, lecture=lecture)
    await mark_complete(lecture_id, version_id=version.id)

    # T-124 (#28, #41): a second, separate LLM call for teacher-facing delivery
    # tips — chained as its own Celery task (not run inline here) so a slow or
    # failing tips call can never affect this lecture's already-succeeded status
    # or eat into this task's soft_time_limit.
    from app.features.lectures.tasks import generate_lecture_teacher_tips

    generate_lecture_teacher_tips.apply_async(
        kwargs={
            "lecture_id": lecture_id,
            "school_id": school_id,
            "version_id": version.id,
            "topic": topic,
            "target_language": lang,
        }
    )

    return version.id
