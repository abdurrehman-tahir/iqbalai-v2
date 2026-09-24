"""T-153 — lecture TTS helpers (offline unit tests)."""

from __future__ import annotations

import io
import wave

from app.features.lectures.lecture_tts import (
    _concat_wav,
    _estimate_duration_ms,
    split_sentences,
)


def _make_wav(*, frames: int = 16000, rate: int = 16000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(rate)
        wav_file.writeframes(b"\x00\x00" * frames)
    return buf.getvalue()


def test_split_sentences_basic() -> None:
    assert split_sentences("Hello world. Next one! Third?") == [
        "Hello world.",
        "Next one!",
        "Third?",
    ]


def test_concat_wav_sums_duration() -> None:
    a = _make_wav(frames=8000)
    b = _make_wav(frames=8000)
    combined = _concat_wav([a, b])
    assert _estimate_duration_ms(combined, text="x") == 1000


def test_estimate_non_wav_uses_char_heuristic() -> None:
    ms = _estimate_duration_ms(b"not-a-wav", text="abcdefghijklmn")  # 14 chars
    assert ms == 1000
