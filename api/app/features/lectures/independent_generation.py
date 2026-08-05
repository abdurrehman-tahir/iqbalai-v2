"""Independent teacher stripped-variant generation pipeline — T-125.

No curriculum RAG (independents have no Grade-Subject/curriculum concept at
all — Step 3 only ever shows their own private references, per flow-5
§3.16), no exam-framework overlay, no live WS token relay (school's T-117
streaming isn't required by this ticket's acceptance criteria — this is a
plain non-streaming ``chat()`` call). Reference retrieval + the out-of-
coverage web-search fallback (T-119) are reused as-is from ``generation.py``
since they're already tenant-agnostic pure/near-pure logic.
"""

from __future__ import annotations

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.lectures.generation import _fetch_web_fallback_chunks, _parse_json_payload
from app.features.lectures.models import (
    IndependentLecture,
    IndependentLectureParagraph,
    IndependentLectureVersion,
    LectureStatus,
)
from app.features.lectures.schemas import ParagraphSourceMetadata, SourceTier
from app.features.library.independent_personal_models import IndependentPersonalContent
from app.infrastructure.llm.client import chat
from app.infrastructure.llm.prompts.lecture_generate_v1 import (
    ChunkRef,
    LectureGenerateInput,
    LectureGenerateOutput,
    LectureParagraphOut,
    render,
)
from app.infrastructure.rag.embedder import independent_personal_collection
from app.infrastructure.rag.retriever import retrieve

logger = structlog.get_logger(__name__)

_TOP_REFERENCE = 8


async def run_independent_lecture_generation(
    session: AsyncSession,
    *,
    lecture_id: str,
    user_id: str,
    topic: str,
    reference_content_ids: list[str],
    teaching_mode: str,
    target_language: str = "en",
) -> str:
    """Reference-only generation (no curriculum tier). Returns the new version id."""
    lecture = await session.get(IndependentLecture, lecture_id)
    if lecture is None or lecture.teacher_user_id != user_id:
        raise ValueError(f"lecture not found: {lecture_id}")

    ref_items: list[IndependentPersonalContent] = []
    for content_id in reference_content_ids:
        item = await session.get(IndependentPersonalContent, content_id)
        if item is not None and item.user_id == user_id:
            ref_items.append(item)

    ref_refs: list[ChunkRef] = []
    if ref_items:
        hits = await retrieve(
            topic,
            independent_personal_collection(user_id),
            top_k=_TOP_REFERENCE,
        )
        allowed = {item.id for item in ref_items}
        titles = {item.id: item.title for item in ref_items}
        for hit in hits:
            raw_payload = hit.get("payload")
            payload: dict[str, object] = raw_payload if isinstance(raw_payload, dict) else {}
            item_id = str(payload.get("library_item_id") or payload.get("item_id") or "")
            if item_id not in allowed:
                continue
            text = str(payload.get("text") or "")
            if not text:
                continue
            ref_refs.append(
                ChunkRef(
                    source_id=str(hit.get("id") or ""),
                    source_label=titles.get(item_id, "Reference"),
                    tier="reference",
                    text=text[:4000],
                )
            )
        ref_refs = ref_refs[:_TOP_REFERENCE]

    # No curriculum tier exists for independents, so an empty reference result
    # escalates straight to tier 3 (web) then tier 4 (honest no-coverage) — the
    # same T-119 cascade, just entering one tier lower than the school pipeline.
    web_refs: list[ChunkRef] = []
    no_coverage = False
    if not ref_refs:
        web_refs = await _fetch_web_fallback_chunks(topic)
        no_coverage = not web_refs
        logger.info(
            "independent_lecture_fallback_tier_used",
            lecture_id=lecture_id,
            tier="web" if web_refs else "no_coverage",
            web_hits=len(web_refs),
        )

    lang = target_language if target_language in ("en", "ur", "sd", "ps") else "en"
    mode = teaching_mode if teaching_mode in ("auto", "manual", "voice_assisted") else "auto"
    prompt = render(
        LectureGenerateInput(
            topic=topic,
            teaching_mode=mode,  # type: ignore[arg-type]
            target_language=lang,  # type: ignore[arg-type]
            curriculum_chunks=[],
            reference_chunks=ref_refs,
            web_chunks=web_refs,
            no_coverage=no_coverage,
        )
    )
    raw = await chat(
        [
            {"role": "system", "content": prompt.system},
            {"role": "user", "content": prompt.user},
        ],
        task="lecture_generate",
        temperature=prompt.temperature,
        max_tokens=prompt.max_tokens,
    )
    try:
        parsed = LectureGenerateOutput.model_validate(_parse_json_payload(raw))
    except Exception:
        logger.warning("independent_lecture_generate_parse_failed", lecture_id=lecture_id)
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
    version = IndependentLectureVersion(lecture_id=lecture.id, version=1, body=body)
    session.add(version)
    await session.flush()

    for ordinal, para in enumerate(parsed.paragraphs):
        tier = SourceTier(para.tier)
        meta = ParagraphSourceMetadata(tier=tier, book_name=para.book_name, chunk_id=para.chunk_id)
        session.add(
            IndependentLectureParagraph(
                lecture_version_id=version.id,
                ordinal=ordinal,
                text=para.text,
                source_metadata_jsonb=meta.to_jsonb(),
            )
        )

    lecture.current_version_id = version.id
    lecture.title = parsed.title[:500]
    lecture.status = LectureStatus.READY_FOR_EDIT
    await session.commit()

    logger.info(
        "independent_lecture_generation_persisted",
        lecture_id=lecture_id,
        version_id=version.id,
        paragraph_count=len(parsed.paragraphs),
    )
    return version.id
