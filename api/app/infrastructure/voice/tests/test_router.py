"""Voice (STT/TTS) router tests — T-121.

Model/network calls are mocked at the router's own internal seams
(`_get_whisper_model`, `_get_piper_voice`, `edge_tts.Communicate`, `httpx`) —
these are real, installed packages (verified via PyPI download, not
hallucinated), but loading actual model weights is out of scope for a unit
test, exactly like `stream_chat`/`web_search` are mocked elsewhere.
"""

from __future__ import annotations

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.infrastructure.voice import router as voice_router
from app.infrastructure.voice.router import VoiceUnavailableError


@pytest.fixture(autouse=True)
def _reset_caches() -> Generator[None, None, None]:
    voice_router._whisper_model = None
    voice_router._piper_voices = {}
    yield
    voice_router._whisper_model = None
    voice_router._piper_voices = {}


class _FakeSegment:
    def __init__(self, text: str) -> None:
        self.text = text


@pytest.mark.asyncio
async def test_transcribe_joins_segment_text(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_model = MagicMock()
    fake_model.transcribe.return_value = (
        [_FakeSegment(" Add an example "), _FakeSegment("about Newton's third law. ")],
        MagicMock(),
    )
    monkeypatch.setattr(voice_router, "_get_whisper_model", lambda: fake_model)

    result = await voice_router.transcribe(b"fake-audio-bytes", language="en")

    assert result == "Add an example about Newton's third law."
    fake_model.transcribe.assert_called_once()
    assert fake_model.transcribe.call_args.kwargs["language"] == "en"


@pytest.mark.asyncio
async def test_synthesize_en_uses_piper(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fake_synthesize_wav(text: str, wav_file: Any) -> None:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(22050)
        wav_file.writeframes(b"\x00\x00" * 100)

    fake_voice = MagicMock()
    fake_voice.synthesize_wav.side_effect = _fake_synthesize_wav
    monkeypatch.setattr(voice_router, "_get_piper_voice", lambda language: fake_voice)

    audio = await voice_router.synthesize("Adding an example.", language="en")

    assert audio.startswith(b"RIFF")  # real WAV container header
    assert len(audio) > 44  # header + at least some frames


@pytest.mark.asyncio
async def test_synthesize_en_without_provisioned_voice_raises_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(voice_router, "_piper_model_path", lambda language: "")

    with pytest.raises(VoiceUnavailableError) as exc_info:
        await voice_router.synthesize("Hello", language="en")

    assert exc_info.value.language == "en"


@pytest.mark.asyncio
async def test_synthesize_ps_uses_edge_tts(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FakeCommunicate:
        def __init__(self, text: str, voice: str) -> None:
            self.text = text
            self.voice = voice

        async def stream(self) -> Any:
            yield {"type": "audio", "data": b"chunk-one-"}
            yield {"type": "WordBoundary", "data": b""}
            yield {"type": "audio", "data": b"chunk-two"}

    import edge_tts

    monkeypatch.setattr(edge_tts, "Communicate", _FakeCommunicate)

    audio = await voice_router.synthesize("Da Newton dradditha qanoon", language="ps")

    assert audio == b"chunk-one-chunk-two"


@pytest.mark.asyncio
async def test_synthesize_ps_no_audio_raises_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    class _EmptyCommunicate:
        def __init__(self, text: str, voice: str) -> None:
            pass

        async def stream(self) -> Any:
            return
            yield  # pragma: no cover - makes this an async generator

    import edge_tts

    monkeypatch.setattr(edge_tts, "Communicate", _EmptyCommunicate)

    with pytest.raises(VoiceUnavailableError) as exc_info:
        await voice_router.synthesize("Hello", language="ps")

    assert exc_info.value.language == "ps"


@pytest.mark.asyncio
async def test_synthesize_sd_without_url_raises_unavailable() -> None:
    with pytest.raises(VoiceUnavailableError) as exc_info:
        await voice_router.synthesize("Hello", language="sd")

    assert exc_info.value.language == "sd"
    assert "not provisioned" in exc_info.value.reason


@pytest.mark.asyncio
async def test_synthesize_sd_calls_configured_ai4bharat_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "AI4BHARAT_TTS_URL", "http://ai4bharat.local")
    monkeypatch.setattr(voice_router, "get_settings", lambda: settings)

    mock_response = MagicMock()
    mock_response.content = b"sindhi-audio-bytes"
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    import httpx

    monkeypatch.setattr(httpx, "AsyncClient", lambda **_kwargs: mock_client)

    audio = await voice_router.synthesize("Hello", language="sd")

    assert audio == b"sindhi-audio-bytes"
    mock_client.post.assert_called_once()
    assert mock_client.post.call_args.args[0] == "http://ai4bharat.local/synthesize"
