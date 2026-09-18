"""Voice conversation session service — independent schema (T-125).

Mirrors ``voice_session.py`` field-for-field, scoped to ``Independent*``
model classes (this codebase routes schemas via separate ORM classes per
tenant, not a runtime schema_translate_map).
"""

from __future__ import annotations

import json
import re
from typing import Any, cast

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.lectures.independent_repository import (
    IndependentLectureParagraphRepository,
    IndependentLectureVoiceSessionRepository,
    IndependentLectureVoiceTurnRepository,
)
from app.features.lectures.models import (
    IndependentLecture,
    IndependentLectureParagraph,
    IndependentLectureVersion,
    IndependentLectureVoiceSession,
    IndependentLectureVoiceTurn,
)
from app.features.lectures.schemas import (
    ParagraphSourceMetadata,
    SourceTier,
    VoiceEditOp,
    VoiceEditOperation,
)
from app.infrastructure.llm.client import chat
from app.infrastructure.llm.prompts.lecture_voice_edit_v1 import (
    PROMPT_VERSION,
    DraftParagraphRef,
    VoiceEditInput,
    VoiceEditOutput,
    render,
)
from app.infrastructure.storage.client import upload_bytes
from app.infrastructure.voice.router import (
    SupportedLanguage,
    VoiceUnavailableError,
    synthesize,
    transcribe,
)

logger = structlog.get_logger(__name__)

_AUDIO_BUCKET = "audio"
_JSON_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)
_SUPPORTED_LANGUAGES = ("en", "ur", "sd", "ps")


class VoiceSessionConflictError(Exception):
    """Another active session already exists for this teacher+lecture (mirrors T-121)."""


def _resolve_language(target_language: str) -> str:
    return target_language if target_language in _SUPPORTED_LANGUAGES else "en"


async def open_session(
    session: AsyncSession, *, lecture: IndependentLecture, teacher_user_id: str
) -> IndependentLectureVoiceSession:
    repo = IndependentLectureVoiceSessionRepository(session)
    existing = await repo.get_active_for_teacher_and_lecture(
        teacher_user_id=teacher_user_id, lecture_id=lecture.id
    )
    if existing is not None:
        raise VoiceSessionConflictError("voice session in progress in another tab")

    voice_session = IndependentLectureVoiceSession(
        lecture_id=lecture.id, teacher_user_id=teacher_user_id
    )
    logger.info(
        "independent_voice_session_opened", lecture_id=lecture.id, teacher_user_id=teacher_user_id
    )
    return await repo.create(voice_session)


async def close_session(
    session: AsyncSession, voice_session: IndependentLectureVoiceSession
) -> IndependentLectureVoiceSession:
    logger.info(
        "independent_voice_session_closed",
        session_id=voice_session.id,
        lecture_id=voice_session.lecture_id,
    )
    return await IndependentLectureVoiceSessionRepository(session).end(voice_session)


async def _apply_edit_operation(
    session: AsyncSession, *, lecture: IndependentLecture, operation: VoiceEditOperation
) -> IndependentLectureVersion | None:
    """Applies insert/replace/append as a NEW immutable version (mirrors T-121 §4.18)."""
    if operation.op == VoiceEditOp.NONE:
        return None
    if lecture.current_version_id is None:
        raise ValueError("lecture has no current version to edit")

    paragraphs = await IndependentLectureParagraphRepository(session).list_by_version(
        lecture.current_version_id
    )
    rows: list[tuple[str, dict[str, Any]]] = [
        (p.text, dict(p.source_metadata_jsonb)) for p in paragraphs
    ]
    voice_meta = ParagraphSourceMetadata(tier=SourceTier.AI_KNOWLEDGE).to_jsonb()

    if operation.op == VoiceEditOp.APPEND:
        rows.append((operation.text or "", voice_meta))
    elif operation.op == VoiceEditOp.INSERT:
        insert_idx = operation.ordinal if operation.ordinal is not None else len(rows)
        insert_idx = max(0, min(insert_idx, len(rows)))
        rows.insert(insert_idx, (operation.text or "", voice_meta))
    elif operation.op == VoiceEditOp.REPLACE:
        replace_idx: int | None = operation.ordinal
        if replace_idx is None or not (0 <= replace_idx < len(rows)):
            raise ValueError(
                f"replace ordinal {replace_idx!r} out of range for {len(rows)} paragraphs"
            )
        rows[replace_idx] = (operation.text or rows[replace_idx][0], rows[replace_idx][1])

    current_version = await session.get(IndependentLectureVersion, lecture.current_version_id)
    next_version_num = (current_version.version + 1) if current_version is not None else 1
    new_version = IndependentLectureVersion(
        lecture_id=lecture.id,
        version=next_version_num,
        body="\n\n".join(text for text, _ in rows),
    )
    session.add(new_version)
    await session.flush()

    for ordinal, (text, meta) in enumerate(rows):
        session.add(
            IndependentLectureParagraph(
                lecture_version_id=new_version.id,
                ordinal=ordinal,
                text=text,
                source_metadata_jsonb=meta,
            )
        )

    lecture.current_version_id = new_version.id
    await session.commit()
    return new_version


def _parse_voice_edit_output(raw: str, transcript: str) -> VoiceEditOutput:
    text = _JSON_FENCE_RE.sub("", raw.strip()).strip()
    try:
        return VoiceEditOutput.model_validate(cast(dict[str, Any], json.loads(text)))
    except Exception:
        logger.warning("independent_voice_edit_parse_failed", prompt_version=PROMPT_VERSION)
        return VoiceEditOutput(
            op="none", confirmation=f'Did you mean: "{transcript}"? Please try again.'
        )


async def process_turn(
    session: AsyncSession,
    *,
    voice_session: IndependentLectureVoiceSession,
    lecture: IndependentLecture,
    audio_bytes: bytes,
    target_language: str,
) -> tuple[IndependentLectureVoiceTurn, bytes | None, str | None]:
    """One STT -> LLM -> draft-edit -> TTS round trip (mirrors T-121).

    Returns ``(turn, tts_audio_or_None, unavailable_notice_or_None)``.
    """
    lang = _resolve_language(target_language)
    transcript = await transcribe(audio_bytes, language=lang)

    paragraphs: list[IndependentLectureParagraph] = []
    if lecture.current_version_id is not None:
        paragraphs = await IndependentLectureParagraphRepository(session).list_by_version(
            lecture.current_version_id
        )

    prompt = render(
        VoiceEditInput(
            instruction=transcript,
            target_language=lang,  # type: ignore[arg-type]
            draft_paragraphs=[
                DraftParagraphRef(ordinal=p.ordinal, text=p.text) for p in paragraphs
            ],
        )
    )
    raw = await chat(
        [
            {"role": "system", "content": prompt.system},
            {"role": "user", "content": prompt.user},
        ],
        task="lecture_voice_edit",
        temperature=prompt.temperature,
        max_tokens=prompt.max_tokens,
    )
    parsed = _parse_voice_edit_output(raw, transcript)

    operation = VoiceEditOperation(
        op=VoiceEditOp(parsed.op), ordinal=parsed.ordinal, text=parsed.text
    )
    await _apply_edit_operation(session, lecture=lecture, operation=operation)

    turns_repo = IndependentLectureVoiceTurnRepository(session)
    ordinal = await turns_repo.count_for_session(voice_session.id)

    storage_key = f"voice-sessions/{voice_session.id}/{ordinal}.webm"
    upload_bytes(_AUDIO_BUCKET, storage_key, audio_bytes, content_type="audio/webm")

    turn = await turns_repo.create(
        IndependentLectureVoiceTurn(
            session_id=voice_session.id,
            ordinal=ordinal,
            transcript=transcript,
            ai_response_text=parsed.confirmation,
            edit_operation_jsonb=operation.to_jsonb(),
            audio_storage_key=storage_key,
        )
    )

    tts_audio: bytes | None = None
    unavailable_notice: str | None = None
    try:
        tts_audio = await synthesize(parsed.confirmation, language=cast(SupportedLanguage, lang))
    except VoiceUnavailableError as exc:
        unavailable_notice = f"voice not yet available in {exc.language}; reading aloud disabled."
        logger.info("independent_voice_tts_unavailable", language=exc.language, reason=exc.reason)

    return turn, tts_audio, unavailable_notice
