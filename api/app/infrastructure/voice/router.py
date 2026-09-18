"""Voice (STT/TTS) router — the ONLY entry point for voice I/O (T-121, STACK_LOCK §4.4).

Mirrors ``infrastructure/rag/embedder.py``'s local/service duality: STT
(faster-whisper) and Piper TTS run in-process, lazy-loaded on first use —
models are provisioned separately (env-configured paths / HF Hub auto-
download), not bundled here. Never a bypass of the abstraction: nothing
outside this module imports ``faster_whisper``, ``piper``, or ``edge_tts``.

Language routing for TTS is locked (STACK_LOCK §4.4):
  en, ur -> Piper (self-hosted, fast path)
  ps     -> Edge-TTS (Microsoft public endpoint, unsupported)
  sd     -> AI4Bharat (self-hosted) — no verified self-hostable package at
            launch; raises VoiceUnavailableError until AI4BHARAT_TTS_URL is
            provisioned (see T-121 PR notes).
"""

from __future__ import annotations

import asyncio
import io
import wave
from typing import Any, Literal

import structlog

from app.config import get_settings

logger = structlog.get_logger(__name__)

SupportedLanguage = Literal["en", "ur", "sd", "ps"]

_whisper_model: Any | None = None
_piper_voices: dict[str, Any] = {}


class VoiceUnavailableError(Exception):
    """STT/TTS not provisioned for this language — the locked fallback (flow-5 §5.4):
    "TTS voice not available for selected language: fallback to text response with
    notification 'voice not yet available in [language]; reading aloud disabled.'"
    """

    def __init__(self, language: str, reason: str) -> None:
        self.language = language
        self.reason = reason
        super().__init__(f"voice unavailable for {language!r}: {reason}")


def _get_whisper_model() -> Any:
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel

        settings = get_settings()
        logger.info(
            "stt_model_loading", model_size=settings.STT_MODEL_SIZE, device=settings.STT_DEVICE
        )
        _whisper_model = WhisperModel(
            settings.STT_MODEL_SIZE,
            device=settings.STT_DEVICE,
            compute_type=settings.STT_COMPUTE_TYPE,
            download_root=settings.STT_DOWNLOAD_ROOT or None,
            local_files_only=settings.STT_LOCAL_FILES_ONLY,
        )
        logger.info("stt_model_loaded", model_size=settings.STT_MODEL_SIZE)
    return _whisper_model


def _transcribe_sync(audio_bytes: bytes, language: str | None) -> str:
    model = _get_whisper_model()
    segments, _info = model.transcribe(io.BytesIO(audio_bytes), language=language)
    return " ".join(segment.text.strip() for segment in segments).strip()


async def transcribe(audio_bytes: bytes, *, language: str | None = None) -> str:
    """STT via faster-whisper (all languages, STACK_LOCK §4.4).

    CPU-bound (CTranslate2 inference) — run off the event loop. ``language=None``
    lets Whisper auto-detect.
    """
    return await asyncio.to_thread(_transcribe_sync, audio_bytes, language)


def _piper_model_path(language: str) -> str:
    settings = get_settings()
    return {"en": settings.PIPER_VOICE_EN_PATH, "ur": settings.PIPER_VOICE_UR_PATH}.get(
        language, ""
    )


def _get_piper_voice(language: str) -> Any:
    if language in _piper_voices:
        return _piper_voices[language]

    model_path = _piper_model_path(language)
    if not model_path:
        raise VoiceUnavailableError(language, "Piper voice model not provisioned")

    from piper import PiperVoice

    logger.info("tts_piper_voice_loading", language=language, model_path=model_path)
    voice = PiperVoice.load(model_path)
    _piper_voices[language] = voice
    logger.info("tts_piper_voice_loaded", language=language)
    return voice


def _synthesize_piper_sync(text: str, language: str) -> bytes:
    voice = _get_piper_voice(language)
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        voice.synthesize_wav(text, wav_file)
    return buffer.getvalue()


async def _synthesize_piper(text: str, language: str) -> bytes:
    try:
        return await asyncio.to_thread(_synthesize_piper_sync, text, language)
    except VoiceUnavailableError:
        raise
    except Exception as exc:
        logger.error("tts_piper_failed", language=language, error=str(exc))
        raise VoiceUnavailableError(language, str(exc)) from exc


async def _synthesize_edge_tts(text: str, *, voice: str, language: str) -> bytes:
    import edge_tts

    try:
        communicate = edge_tts.Communicate(text, voice)
        chunks = bytearray()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                chunks.extend(chunk["data"])
        if not chunks:
            raise VoiceUnavailableError(language, "Edge-TTS returned no audio")
        return bytes(chunks)
    except VoiceUnavailableError:
        raise
    except Exception as exc:
        logger.error("tts_edge_failed", language=language, error=str(exc))
        raise VoiceUnavailableError(language, str(exc)) from exc


async def _synthesize_ai4bharat(text: str, language: str) -> bytes:
    settings = get_settings()
    if not settings.AI4BHARAT_TTS_URL:
        raise VoiceUnavailableError(language, "AI4Bharat TTS not provisioned")

    import httpx

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{settings.AI4BHARAT_TTS_URL}/synthesize",
                json={"text": text, "language": language},
            )
            response.raise_for_status()
            return response.content
    except httpx.HTTPError as exc:
        logger.error("tts_ai4bharat_failed", language=language, error=str(exc))
        raise VoiceUnavailableError(language, str(exc)) from exc


async def synthesize(text: str, *, language: SupportedLanguage) -> bytes:
    """TTS routed by language (STACK_LOCK §4.4). Returns WAV/audio bytes.

    Always raises :class:`VoiceUnavailableError` rather than returning empty
    audio when a provider isn't reachable/provisioned — callers implement the
    locked text-only fallback (flow-5 §5.4), never a silent failure.
    """
    if language in ("en", "ur"):
        return await _synthesize_piper(text, language)
    if language == "ps":
        settings = get_settings()
        return await _synthesize_edge_tts(text, voice=settings.EDGE_TTS_VOICE_PS, language=language)
    if language == "sd":
        return await _synthesize_ai4bharat(text, language)
    raise VoiceUnavailableError(language, "unsupported language")
