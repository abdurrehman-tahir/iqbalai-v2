"""Independent voice session service tests — T-125 (mirrors T-121's test_voice_session.py).

The edit-application / JSON-parsing logic is a byte-for-byte mirror of the
already-thoroughly-tested school variant (339 lines in test_voice_session.py)
— this file covers the independent-specific wiring (session lifecycle,
Independent* model usage, process_turn end-to-end) rather than re-deriving
every ordinal-shifting edge case already proven against identical logic.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.features.lectures import independent_voice_session as voice_session
from app.features.lectures.models import (
    IndependentLecture,
    IndependentLectureVersion,
    IndependentLectureVoiceSession,
    LectureStatus,
)
from app.features.lectures.schemas import VoiceEditOp, VoiceEditOperation
from app.infrastructure.voice.router import VoiceUnavailableError


def _fake_lecture(**overrides: Any) -> IndependentLecture:
    defaults: dict[str, Any] = {
        "id": "lec-1",
        "teacher_user_id": "teacher-1",
        "title": "Newton's Laws",
        "topic": "Newton's Laws",
        "status": LectureStatus.READY_FOR_EDIT,
        "current_version_id": "ver-1",
    }
    defaults.update(overrides)
    return IndependentLecture(**defaults)


class _FakeParagraph:
    def __init__(self, ordinal: int, text: str, tier: str = "ai_knowledge") -> None:
        self.ordinal = ordinal
        self.text = text
        self.source_metadata_jsonb = {"tier": tier}


@pytest.mark.asyncio
async def test_open_session_creates_new_session(monkeypatch: pytest.MonkeyPatch) -> None:
    session = AsyncMock()
    lecture = _fake_lecture()

    created = IndependentLectureVoiceSession(lecture_id="lec-1", teacher_user_id="teacher-1")
    fake_repo = MagicMock(
        get_active_for_teacher_and_lecture=AsyncMock(return_value=None),
        create=AsyncMock(return_value=created),
    )
    monkeypatch.setattr(
        "app.features.lectures.independent_voice_session.IndependentLectureVoiceSessionRepository",
        lambda _session: fake_repo,
    )

    result = await voice_session.open_session(session, lecture=lecture, teacher_user_id="teacher-1")

    assert result is created
    fake_repo.create.assert_awaited_once()


@pytest.mark.asyncio
async def test_open_session_conflicts_when_already_active(monkeypatch: pytest.MonkeyPatch) -> None:
    session = AsyncMock()
    lecture = _fake_lecture()
    existing = IndependentLectureVoiceSession(lecture_id="lec-1", teacher_user_id="teacher-1")

    fake_repo = MagicMock(get_active_for_teacher_and_lecture=AsyncMock(return_value=existing))
    monkeypatch.setattr(
        "app.features.lectures.independent_voice_session.IndependentLectureVoiceSessionRepository",
        lambda _session: fake_repo,
    )

    with pytest.raises(voice_session.VoiceSessionConflictError):
        await voice_session.open_session(session, lecture=lecture, teacher_user_id="teacher-1")


@pytest.mark.asyncio
async def test_close_session_ends_it(monkeypatch: pytest.MonkeyPatch) -> None:
    session = AsyncMock()
    active = IndependentLectureVoiceSession(
        id="vs-1", lecture_id="lec-1", teacher_user_id="teacher-1"
    )
    ended = MagicMock()
    fake_repo = MagicMock(end=AsyncMock(return_value=ended))
    monkeypatch.setattr(
        "app.features.lectures.independent_voice_session.IndependentLectureVoiceSessionRepository",
        lambda _session: fake_repo,
    )

    result = await voice_session.close_session(session, active)

    assert result is ended
    fake_repo.end.assert_awaited_once_with(active)


@pytest.mark.asyncio
async def test_apply_edit_append_adds_paragraph_and_bumps_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = AsyncMock()
    lecture = _fake_lecture()
    existing = [_FakeParagraph(0, "First paragraph.")]

    current_version = MagicMock()
    current_version.version = 1
    session.get = AsyncMock(return_value=current_version)
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    added: list[Any] = []
    session.add = MagicMock(side_effect=lambda obj: added.append(obj))

    monkeypatch.setattr(
        "app.features.lectures.independent_voice_session.IndependentLectureParagraphRepository",
        lambda _session: MagicMock(list_by_version=AsyncMock(return_value=existing)),
    )

    await voice_session._apply_edit_operation(
        session,
        lecture=lecture,
        operation=VoiceEditOperation(op=VoiceEditOp.APPEND, text="A new example."),
    )

    from app.features.lectures.models import IndependentLectureParagraph

    versions = [o for o in added if isinstance(o, IndependentLectureVersion)]
    paragraphs = [o for o in added if isinstance(o, IndependentLectureParagraph)]
    assert len(versions) == 1
    assert versions[0].version == 2
    assert len(paragraphs) == 2
    assert paragraphs[1].text == "A new example."
    assert lecture.current_version_id == versions[0].id


@pytest.mark.asyncio
async def test_process_turn_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    session = AsyncMock()
    lecture = _fake_lecture()
    active_session = IndependentLectureVoiceSession(
        id="vs-1", lecture_id="lec-1", teacher_user_id="teacher-1"
    )

    monkeypatch.setattr(
        "app.features.lectures.independent_voice_session.transcribe",
        AsyncMock(return_value="add an example about Newton's third law"),
    )
    monkeypatch.setattr(
        "app.features.lectures.independent_voice_session.IndependentLectureParagraphRepository",
        lambda _session: MagicMock(list_by_version=AsyncMock(return_value=[])),
    )
    monkeypatch.setattr(
        "app.features.lectures.independent_voice_session.chat",
        AsyncMock(
            return_value=(
                '{"op": "append", "text": "For every action there is an equal and '
                'opposite reaction.", "confirmation": "Adding an example about Newton\'s third law."}'
            )
        ),
    )
    monkeypatch.setattr(
        "app.features.lectures.independent_voice_session._apply_edit_operation",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        "app.features.lectures.independent_voice_session.upload_bytes",
        MagicMock(return_value="key"),
    )
    monkeypatch.setattr(
        "app.features.lectures.independent_voice_session.synthesize",
        AsyncMock(return_value=b"tts-audio-bytes"),
    )

    created_turn = MagicMock()
    created_turn.transcript = "add an example about Newton's third law"
    created_turn.ai_response_text = "Adding an example about Newton's third law."
    fake_turns_repo = MagicMock(
        count_for_session=AsyncMock(return_value=0),
        create=AsyncMock(return_value=created_turn),
    )
    monkeypatch.setattr(
        "app.features.lectures.independent_voice_session.IndependentLectureVoiceTurnRepository",
        lambda _session: fake_turns_repo,
    )

    turn, tts_audio, unavailable_notice = await voice_session.process_turn(
        session,
        voice_session=active_session,
        lecture=lecture,
        audio_bytes=b"raw-audio",
        target_language="en",
    )

    assert turn is created_turn
    assert tts_audio == b"tts-audio-bytes"
    assert unavailable_notice is None
    fake_turns_repo.create.assert_awaited_once()


@pytest.mark.asyncio
async def test_process_turn_tts_unavailable_degrades_to_text_notice(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = AsyncMock()
    lecture = _fake_lecture()
    active_session = IndependentLectureVoiceSession(
        id="vs-1", lecture_id="lec-1", teacher_user_id="teacher-1"
    )

    monkeypatch.setattr(
        "app.features.lectures.independent_voice_session.transcribe",
        AsyncMock(return_value="what topic is this"),
    )
    monkeypatch.setattr(
        "app.features.lectures.independent_voice_session.IndependentLectureParagraphRepository",
        lambda _session: MagicMock(list_by_version=AsyncMock(return_value=[])),
    )
    monkeypatch.setattr(
        "app.features.lectures.independent_voice_session.chat",
        AsyncMock(return_value='{"op": "none", "confirmation": "This lecture is about..."}'),
    )
    monkeypatch.setattr(
        "app.features.lectures.independent_voice_session._apply_edit_operation",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        "app.features.lectures.independent_voice_session.upload_bytes",
        MagicMock(return_value="key"),
    )

    async def _raise_unavailable(*_a: Any, **_k: Any) -> bytes:
        raise VoiceUnavailableError(language="sd", reason="no_provider")

    monkeypatch.setattr(
        "app.features.lectures.independent_voice_session.synthesize", _raise_unavailable
    )
    monkeypatch.setattr(
        "app.features.lectures.independent_voice_session.IndependentLectureVoiceTurnRepository",
        lambda _session: MagicMock(
            count_for_session=AsyncMock(return_value=0),
            create=AsyncMock(return_value=MagicMock()),
        ),
    )

    _turn, tts_audio, unavailable_notice = await voice_session.process_turn(
        session,
        voice_session=active_session,
        lecture=lecture,
        audio_bytes=b"raw-audio",
        target_language="sd",
    )

    assert tts_audio is None
    assert unavailable_notice is not None
    assert "sd" in unavailable_notice
