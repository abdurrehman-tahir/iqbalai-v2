"""Lecture TTS generation + MinIO cache (T-153, Flow 6 §3.2 / #54).

Uses ``infrastructure.voice.router.synthesize`` (STACK_LOCK §4.4). Celery task
name ``tts.generate_audio`` per Flow 6 / ARCH refs. Sentence-level alignment
is produced by synthesizing per sentence and measuring WAV durations (Piper)
or estimating from byte size for non-WAV providers.
"""

from __future__ import annotations

import io
import re
import wave
from typing import Any, Literal

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.exceptions import NotFoundError, PermissionDeniedError, ValidationError
from app.features.lectures.models import (
    LectureAudioCacheStatus,
    LectureStatus,
    SchoolLecture,
    SchoolLectureAudioCache,
    SchoolLectureParagraph,
)
from app.features.lectures.repository import LectureParagraphRepository, LectureRepository
from app.features.lectures.schemas import (
    LectureAudioAlignmentSpan,
    LectureAudioCacheRead,
    LectureAudioRequest,
)
from app.features.lectures.service import LectureService
from app.features.users.models import User, UserRole
from app.features.users.repository import UserRepository
from app.infrastructure.storage.client import presigned_get_url, upload_bytes
from app.infrastructure.voice.router import SupportedLanguage, VoiceUnavailableError, synthesize

logger = structlog.get_logger(__name__)

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?。؟۔])\s+")
SupportedLang = Literal["en", "ur", "sd", "ps"]
_AUDIO_URL_TTL_SECONDS = 300


def split_sentences(text: str) -> list[str]:
    cleaned = " ".join(text.split())
    if not cleaned:
        return []
    parts = _SENTENCE_SPLIT.split(cleaned)
    return [p.strip() for p in parts if p.strip()]


def _wav_duration_ms(audio: bytes) -> int:
    with wave.open(io.BytesIO(audio), "rb") as wav_file:
        frames = wav_file.getnframes()
        rate = wav_file.getframerate()
        if rate <= 0:
            return 0
        return int(frames / rate * 1000)


def _estimate_duration_ms(audio: bytes, *, text: str) -> int:
    """Fallback when container isn't WAV (Edge-TTS / AI4Bharat). ~14 chars/sec."""
    if len(audio) >= 44 and audio[:4] == b"RIFF":
        try:
            return _wav_duration_ms(audio)
        except wave.Error:
            pass
    chars = max(len(text), 1)
    return max(int(chars / 14.0 * 1000), 250)


def _concat_wav(chunks: list[bytes]) -> bytes:
    if not chunks:
        return b""
    if len(chunks) == 1:
        return chunks[0]
    params: tuple[int, int, int, int, str, str] | None = None
    frames = bytearray()
    for chunk in chunks:
        with wave.open(io.BytesIO(chunk), "rb") as src:
            if params is None:
                params = src.getparams()
            frames.extend(src.readframes(src.getnframes()))
    assert params is not None
    out = io.BytesIO()
    with wave.open(out, "wb") as dest:
        dest.setparams(params)
        dest.writeframes(bytes(frames))
    return out.getvalue()


class LectureAudioCacheRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_lecture_language(
        self, lecture_id: str, language: str
    ) -> SchoolLectureAudioCache | None:
        result = await self._session.execute(
            select(SchoolLectureAudioCache).where(
                SchoolLectureAudioCache.lecture_id == lecture_id,
                SchoolLectureAudioCache.language == language,
            )
        )
        return result.scalar_one_or_none()

    async def list_by_lecture(self, lecture_id: str) -> list[SchoolLectureAudioCache]:
        result = await self._session.execute(
            select(SchoolLectureAudioCache).where(SchoolLectureAudioCache.lecture_id == lecture_id)
        )
        return list(result.scalars().all())

    async def create(self, row: SchoolLectureAudioCache) -> SchoolLectureAudioCache:
        self._session.add(row)
        await self._session.commit()
        await self._session.refresh(row)
        return row

    async def save(self, row: SchoolLectureAudioCache) -> SchoolLectureAudioCache:
        await self._session.commit()
        await self._session.refresh(row)
        return row


def _audio_url_for(row: SchoolLectureAudioCache) -> str | None:
    if row.status != LectureAudioCacheStatus.READY or not row.audio_storage_key:
        return None
    settings = get_settings()
    return presigned_get_url(
        settings.MINIO_BUCKET_AUDIO,
        row.audio_storage_key,
        expires_seconds=_AUDIO_URL_TTL_SECONDS,
    )


def _to_read(row: SchoolLectureAudioCache) -> LectureAudioCacheRead:
    spans: list[LectureAudioAlignmentSpan] = []
    raw = row.alignment_jsonb or []
    for item in raw:
        spans.append(LectureAudioAlignmentSpan.model_validate(item))
    lang: Literal["en", "ur", "sd", "ps"] = (
        row.language if row.language in ("en", "ur", "sd", "ps") else "en"  # type: ignore[assignment]
    )
    return LectureAudioCacheRead(
        id=row.id,
        lecture_id=row.lecture_id,
        lecture_version_id=row.lecture_version_id,
        language=lang,
        status=row.status.value,  # type: ignore[arg-type]
        audio_url=_audio_url_for(row),
        content_type=row.content_type,
        byte_size=row.byte_size,
        duration_ms=row.duration_ms,
        alignment=spans,
        error_message=row.error_message,
    )


class LectureTtsService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._users = UserRepository(session)
        self._lectures = LectureRepository(session)
        self._paragraphs = LectureParagraphRepository(session)
        self._caches = LectureAudioCacheRepository(session)
        self._lecture_svc = LectureService(session)

    async def _require_student(self, claims: dict[str, object]) -> User:
        user = await self._users.get_by_authentik_id(str(claims.get("sub", "")))
        if user is None or user.deleted_at is not None:
            raise NotFoundError("User profile not found")
        if user.role != UserRole.STUDENT:
            raise PermissionDeniedError("Student role required")
        return user

    async def _require_accessible_published(self, student: User, lecture_id: str) -> SchoolLecture:
        lecture = await self._lectures.get_by_id(lecture_id)
        if lecture is None or lecture.status != LectureStatus.PUBLISHED:
            raise NotFoundError("Lecture not found")
        if lecture.current_version_id is None:
            raise NotFoundError("Lecture has no published version")
        if not await self._lecture_svc.student_can_access_lecture(student, lecture):
            raise PermissionDeniedError("Not enrolled or access-restricted for this lecture")
        return lecture

    async def request_or_get(
        self, claims: dict[str, object], lecture_id: str, payload: LectureAudioRequest
    ) -> LectureAudioCacheRead:
        """Lazy TTS: return ready cache or enqueue generation (T-153)."""
        student = await self._require_student(claims)
        lecture = await self._require_accessible_published(student, lecture_id)
        if lecture.school_id is None:
            raise ValidationError("Lecture is missing school_id")

        language = payload.language
        row = await self._caches.get_by_lecture_language(lecture_id, language)
        if (
            row is not None
            and row.status == LectureAudioCacheStatus.READY
            and row.lecture_version_id == lecture.current_version_id
            and row.audio_storage_key
        ):
            return _to_read(row)

        # Idempotent: matching pending job → do not re-enqueue.
        if (
            row is not None
            and row.status == LectureAudioCacheStatus.PENDING
            and row.lecture_version_id == lecture.current_version_id
        ):
            return _to_read(row)

        if row is None:
            row = await self._caches.create(
                SchoolLectureAudioCache(
                    lecture_id=lecture_id,
                    lecture_version_id=lecture.current_version_id,
                    language=language,
                    status=LectureAudioCacheStatus.PENDING,
                )
            )
        else:
            row.lecture_version_id = lecture.current_version_id
            row.status = LectureAudioCacheStatus.PENDING
            row.error_message = None
            row = await self._caches.save(row)

        from app.features.lectures.tasks import generate_lecture_audio

        generate_lecture_audio.delay(
            lecture_id=lecture_id,
            school_id=lecture.school_id,
            language=language,
            cache_id=row.id,
        )
        return _to_read(row)

    async def get_status(
        self, claims: dict[str, object], lecture_id: str, language: str
    ) -> LectureAudioCacheRead:
        student = await self._require_student(claims)
        lecture = await self._require_accessible_published(student, lecture_id)
        row = await self._caches.get_by_lecture_language(lecture_id, language)
        if row is None:
            raise NotFoundError("Lecture audio cache not found")
        if (
            row.status == LectureAudioCacheStatus.READY
            and row.lecture_version_id != lecture.current_version_id
        ):
            row.status = LectureAudioCacheStatus.INVALIDATED
            row = await self._caches.save(row)
        return _to_read(row)

    async def download_url(self, claims: dict[str, object], lecture_id: str, language: str) -> str:
        """Presigned download URL for ready audio (T-154 download control)."""
        read = await self.get_status(claims, lecture_id, language)
        if read.status != "ready" or not read.audio_url:
            raise ValidationError("Lecture audio is not ready for download")
        return read.audio_url


async def invalidate_lecture_audio_caches(session: AsyncSession, lecture_id: str) -> int:
    """Soft-invalidate caches after a non-autosave lecture re-edit (T-153).

    Keeps MinIO objects until regen overwrites the key so in-flight plays may
    finish. Status flips to invalidated; alignment cleared.
    """
    repo = LectureAudioCacheRepository(session)
    rows = await repo.list_by_lecture(lecture_id)
    count = 0
    for row in rows:
        if row.status == LectureAudioCacheStatus.INVALIDATED:
            continue
        row.status = LectureAudioCacheStatus.INVALIDATED
        row.alignment_jsonb = None
        row.duration_ms = None
        count += 1
    if count:
        await session.commit()
    return count


async def build_lecture_audio_cache(
    session: AsyncSession,
    *,
    lecture_id: str,
    school_id: str,
    language: SupportedLanguage,
    cache_id: str,
) -> dict[str, Any]:
    """Celery worker body — synthesize, upload, write alignment."""
    caches = LectureAudioCacheRepository(session)
    lectures = LectureRepository(session)
    paragraphs_repo = LectureParagraphRepository(session)

    row = await caches.get_by_lecture_language(lecture_id, language)
    if row is None or row.id != cache_id:
        row = await session.get(SchoolLectureAudioCache, cache_id)
    if row is None:
        return {"status": "missing_cache"}

    lecture = await lectures.get_by_id(lecture_id)
    if lecture is None or lecture.current_version_id is None:
        row.status = LectureAudioCacheStatus.FAILED
        row.error_message = "Lecture or version missing"
        await caches.save(row)
        return {"status": "failed", "error": row.error_message}

    paragraphs = await paragraphs_repo.list_by_version(lecture.current_version_id)
    segments: list[tuple[SchoolLectureParagraph, str]] = []
    for paragraph in paragraphs:
        for sentence in split_sentences(paragraph.text):
            segments.append((paragraph, sentence))

    if not segments:
        row.status = LectureAudioCacheStatus.FAILED
        row.error_message = "Lecture has no speakable text"
        await caches.save(row)
        return {"status": "failed", "error": row.error_message}

    try:
        audio_chunks: list[bytes] = []
        alignment: list[dict[str, object]] = []
        cursor_ms = 0
        ordinal = 0
        for paragraph, sentence in segments:
            chunk = await synthesize(sentence, language=language)
            duration = _estimate_duration_ms(chunk, text=sentence)
            alignment.append(
                {
                    "ordinal": ordinal,
                    "paragraph_id": paragraph.id,
                    "text": sentence,
                    "start_ms": cursor_ms,
                    "end_ms": cursor_ms + duration,
                }
            )
            audio_chunks.append(chunk)
            cursor_ms += duration
            ordinal += 1

        if all(c[:4] == b"RIFF" for c in audio_chunks):
            audio_bytes = _concat_wav(audio_chunks)
            content_type = "audio/wav"
            ext = "wav"
        else:
            audio_bytes = b"".join(audio_chunks)
            content_type = "audio/mpeg"
            ext = "mp3"

        settings = get_settings()
        key = f"audio/{school_id}/{lecture_id}/{language}.{ext}"
        upload_bytes(settings.MINIO_BUCKET_AUDIO, key, audio_bytes, content_type=content_type)

        row.lecture_version_id = lecture.current_version_id
        row.status = LectureAudioCacheStatus.READY
        row.audio_storage_key = key
        row.content_type = content_type
        row.byte_size = len(audio_bytes)
        row.duration_ms = cursor_ms
        row.alignment_jsonb = alignment
        row.error_message = None
        await caches.save(row)
        logger.info(
            "lecture_audio_ready",
            lecture_id=lecture_id,
            language=language,
            duration_ms=cursor_ms,
            sentences=len(alignment),
        )
        return {"status": "ready", "cache_id": row.id, "duration_ms": cursor_ms}
    except VoiceUnavailableError as exc:
        row.status = LectureAudioCacheStatus.FAILED
        row.error_message = str(exc)
        await caches.save(row)
        logger.warning(
            "lecture_audio_unavailable",
            lecture_id=lecture_id,
            language=language,
            error=str(exc),
        )
        return {"status": "failed", "error": str(exc)}
    except Exception as exc:
        row.status = LectureAudioCacheStatus.FAILED
        row.error_message = str(exc)
        await caches.save(row)
        logger.exception("lecture_audio_failed", lecture_id=lecture_id, language=language)
        return {"status": "failed", "error": str(exc)}
