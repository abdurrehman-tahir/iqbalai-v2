"""Voice session service tests — T-121 (#25)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.features.lectures import voice_session
from app.features.lectures.models import (
    LectureStatus,
    LectureType,
    SchoolLecture,
    SchoolLectureVoiceSession,
    VoiceSessionStatus,
)
from app.features.lectures.schemas import VoiceEditOp, VoiceEditOperation
from app.infrastructure.voice.router import VoiceUnavailableError


def _fake_lecture(**overrides: Any) -> SchoolLecture:
    defaults: dict[str, Any] = {
        "id": "lec-1",
        "school_id": "school-1",
        "teacher_user_id": "teacher-1",
        "title": "Newton's Laws",
        "topic": "Newton's Laws",
        "lecture_type": LectureType.MAIN,
        "status": LectureStatus.READY_FOR_EDIT,
        "current_version_id": "ver-1",
    }
    defaults.update(overrides)
    return SchoolLecture(**defaults)


class _FakeParagraph:
    def __init__(self, ordinal: int, text: str, tier: str = "curriculum") -> None:
        self.ordinal = ordinal
        self.text = text
        self.source_metadata_jsonb = {"tier": tier}


# ---------------------------------------------------------------------------
# _apply_edit_operation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_apply_edit_none_is_a_noop(monkeypatch: pytest.MonkeyPatch) -> None:
    session = AsyncMock()
    lecture = _fake_lecture()

    result = await voice_session._apply_edit_operation(
        session, lecture=lecture, operation=VoiceEditOperation(op=VoiceEditOp.NONE)
    )

    assert result is None
    session.add.assert_not_called()


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
        "app.features.lectures.voice_session.LectureParagraphRepository",
        lambda _session: MagicMock(list_by_version=AsyncMock(return_value=existing)),
    )

    await voice_session._apply_edit_operation(
        session,
        lecture=lecture,
        operation=VoiceEditOperation(op=VoiceEditOp.APPEND, text="A new example."),
    )

    from app.features.lectures.models import SchoolLectureParagraph, SchoolLectureVersion

    versions = [o for o in added if isinstance(o, SchoolLectureVersion)]
    paragraphs = [o for o in added if isinstance(o, SchoolLectureParagraph)]
    assert len(versions) == 1
    assert versions[0].version == 2
    assert len(paragraphs) == 2
    assert paragraphs[1].text == "A new example."
    assert paragraphs[1].source_metadata_jsonb["tier"] == "ai_knowledge"
    assert lecture.current_version_id == versions[0].id


@pytest.mark.asyncio
async def test_apply_edit_insert_shifts_ordinals(monkeypatch: pytest.MonkeyPatch) -> None:
    session = AsyncMock()
    lecture = _fake_lecture()
    existing = [_FakeParagraph(0, "First."), _FakeParagraph(1, "Second.")]

    session.get = AsyncMock(return_value=MagicMock(version=3))
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    added: list[Any] = []
    session.add = MagicMock(side_effect=lambda obj: added.append(obj))

    monkeypatch.setattr(
        "app.features.lectures.voice_session.LectureParagraphRepository",
        lambda _session: MagicMock(list_by_version=AsyncMock(return_value=existing)),
    )

    await voice_session._apply_edit_operation(
        session,
        lecture=lecture,
        operation=VoiceEditOperation(op=VoiceEditOp.INSERT, ordinal=1, text="Inserted."),
    )

    from app.features.lectures.models import SchoolLectureParagraph

    paragraphs = sorted(
        (o for o in added if isinstance(o, SchoolLectureParagraph)), key=lambda p: p.ordinal
    )
    assert [p.text for p in paragraphs] == ["First.", "Inserted.", "Second."]


@pytest.mark.asyncio
async def test_apply_edit_replace_out_of_range_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    session = AsyncMock()
    lecture = _fake_lecture()
    existing = [_FakeParagraph(0, "Only paragraph.")]

    session.get = AsyncMock(return_value=MagicMock(version=1))
    monkeypatch.setattr(
        "app.features.lectures.voice_session.LectureParagraphRepository",
        lambda _session: MagicMock(list_by_version=AsyncMock(return_value=existing)),
    )

    with pytest.raises(ValueError, match="out of range"):
        await voice_session._apply_edit_operation(
            session,
            lecture=lecture,
            operation=VoiceEditOperation(op=VoiceEditOp.REPLACE, ordinal=5, text="x"),
        )


# ---------------------------------------------------------------------------
# _parse_voice_edit_output
# ---------------------------------------------------------------------------


def test_parse_voice_edit_output_valid_json() -> None:
    raw = '{"op": "append", "text": "An example.", "confirmation": "Adding an example."}'
    parsed = voice_session._parse_voice_edit_output(raw, transcript="add an example")
    assert parsed.op == "append"
    assert parsed.text == "An example."


def test_parse_voice_edit_output_malformed_falls_back_to_echo() -> None:
    parsed = voice_session._parse_voice_edit_output("not json at all", transcript="do a thing")
    assert parsed.op == "none"
    assert "do a thing" in parsed.confirmation


# ---------------------------------------------------------------------------
# open_session / close_session
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_open_session_creates_when_none_active(monkeypatch: pytest.MonkeyPatch) -> None:
    session = AsyncMock()
    lecture = _fake_lecture()
    created: SchoolLectureVoiceSession | None = None

    async def _create(voice_sess: SchoolLectureVoiceSession) -> SchoolLectureVoiceSession:
        nonlocal created
        created = voice_sess
        return voice_sess

    fake_repo = MagicMock(
        get_active_for_teacher_and_lecture=AsyncMock(return_value=None),
        create=AsyncMock(side_effect=_create),
    )
    monkeypatch.setattr(
        "app.features.lectures.voice_session.LectureVoiceSessionRepository",
        lambda _session: fake_repo,
    )

    result = await voice_session.open_session(session, lecture=lecture, teacher_user_id="teacher-1")

    assert result is created
    assert result.status == VoiceSessionStatus.ACTIVE


@pytest.mark.asyncio
async def test_open_session_conflicts_when_already_active(monkeypatch: pytest.MonkeyPatch) -> None:
    session = AsyncMock()
    lecture = _fake_lecture()
    existing = SchoolLectureVoiceSession(lecture_id="lec-1", teacher_user_id="teacher-1")

    fake_repo = MagicMock(get_active_for_teacher_and_lecture=AsyncMock(return_value=existing))
    monkeypatch.setattr(
        "app.features.lectures.voice_session.LectureVoiceSessionRepository",
        lambda _session: fake_repo,
    )

    with pytest.raises(voice_session.VoiceSessionConflictError):
        await voice_session.open_session(session, lecture=lecture, teacher_user_id="teacher-1")


# ---------------------------------------------------------------------------
# process_turn
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_process_turn_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    session = AsyncMock()
    lecture = _fake_lecture()
    active_session = SchoolLectureVoiceSession(
        id="vs-1", lecture_id="lec-1", teacher_user_id="teacher-1"
    )

    monkeypatch.setattr(
        "app.features.lectures.voice_session.transcribe",
        AsyncMock(return_value="add an example about Newton's third law"),
    )
    monkeypatch.setattr(
        "app.features.lectures.voice_session.LectureParagraphRepository",
        lambda _session: MagicMock(list_by_version=AsyncMock(return_value=[])),
    )
    monkeypatch.setattr(
        "app.features.lectures.voice_session.chat",
        AsyncMock(
            return_value=(
                '{"op": "append", "text": "For every action there is an equal and '
                'opposite reaction.", "confirmation": "Adding an example about Newton\'s third law."}'
            )
        ),
    )
    monkeypatch.setattr(
        "app.features.lectures.voice_session._apply_edit_operation", AsyncMock(return_value=None)
    )
    monkeypatch.setattr(
        "app.features.lectures.voice_session.upload_bytes", MagicMock(return_value="key")
    )
    monkeypatch.setattr(
        "app.features.lectures.voice_session.synthesize", AsyncMock(return_value=b"tts-audio-bytes")
    )

    created_turn = MagicMock()
    created_turn.transcript = "add an example about Newton's third law"
    created_turn.ai_response_text = "Adding an example about Newton's third law."
    fake_turns_repo = MagicMock(
        count_for_session=AsyncMock(return_value=0),
        create=AsyncMock(return_value=created_turn),
    )
    monkeypatch.setattr(
        "app.features.lectures.voice_session.LectureVoiceTurnRepository",
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
    active_session = SchoolLectureVoiceSession(
        id="vs-1", lecture_id="lec-1", teacher_user_id="teacher-1"
    )

    monkeypatch.setattr(
        "app.features.lectures.voice_session.transcribe",
        AsyncMock(return_value="what topic is this"),
    )
    monkeypatch.setattr(
        "app.features.lectures.voice_session.LectureParagraphRepository",
        lambda _session: MagicMock(list_by_version=AsyncMock(return_value=[])),
    )
    monkeypatch.setattr(
        "app.features.lectures.voice_session.chat",
        AsyncMock(
            return_value='{"op": "none", "confirmation": "This lecture covers Newton\'s Laws."}'
        ),
    )
    monkeypatch.setattr(
        "app.features.lectures.voice_session._apply_edit_operation", AsyncMock(return_value=None)
    )
    monkeypatch.setattr(
        "app.features.lectures.voice_session.upload_bytes", MagicMock(return_value="key")
    )

    async def _raise_unavailable(*_a: Any, **_k: Any) -> bytes:
        raise VoiceUnavailableError("sd", "AI4Bharat TTS not provisioned")

    monkeypatch.setattr("app.features.lectures.voice_session.synthesize", _raise_unavailable)

    created_turn = MagicMock()
    fake_turns_repo = MagicMock(
        count_for_session=AsyncMock(return_value=2),
        create=AsyncMock(return_value=created_turn),
    )
    monkeypatch.setattr(
        "app.features.lectures.voice_session.LectureVoiceTurnRepository",
        lambda _session: fake_turns_repo,
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
