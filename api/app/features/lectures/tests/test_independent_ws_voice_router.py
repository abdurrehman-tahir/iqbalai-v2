"""Independent voice conversation WebSocket tests — T-125 (mirrors T-121's suite).

Uses Starlette's `TestClient.websocket_connect` — same justified exception
as the school variant: httpx has no WebSocket support.
"""

from __future__ import annotations

import base64
from collections.abc import AsyncGenerator
from typing import Any

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from app.core.dependencies import get_db
from app.features.lectures import independent_voice_session as voice_session_module
from app.features.lectures import independent_ws_voice_router as ws_voice_router_module
from app.features.lectures.models import (
    IndependentLecture,
    IndependentLectureVoiceSession,
    LectureStatus,
)

LECTURE = IndependentLecture(
    id="lec-1",
    teacher_user_id="teacher-1",
    title="Newton's Laws",
    topic="Newton's Laws",
    status=LectureStatus.READY_FOR_EDIT,
    current_version_id="ver-1",
)

TEACHER_CLAIMS: dict[str, object] = {
    "sub": "auth-teacher",
    "role": "independent_teacher",
    "user_id": "teacher-1",
}


class _FakeLectureRepo:
    store: dict[str, IndependentLecture] = {LECTURE.id: LECTURE}

    def __init__(self, session: Any) -> None:
        pass

    async def get_by_id(self, lecture_id: str) -> IndependentLecture | None:
        return self.store.get(lecture_id)


async def _fake_db() -> AsyncGenerator[None, None]:
    yield None


@pytest.fixture(autouse=True)
def _patch_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    _FakeLectureRepo.store = {LECTURE.id: LECTURE}
    monkeypatch.setattr(ws_voice_router_module, "IndependentLectureRepository", _FakeLectureRepo)


def _make_app() -> FastAPI:
    app = FastAPI()
    app.include_router(ws_voice_router_module.router)
    app.dependency_overrides[get_db] = _fake_db
    return app


def test_ws_rejects_missing_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _no_auth(websocket: Any) -> None:
        return None

    monkeypatch.setattr(ws_voice_router_module, "authenticate_websocket", _no_auth)
    client = TestClient(_make_app())

    with pytest.raises(Exception) as exc_info:
        with client.websocket_connect("/independent/lectures/lec-1/voice"):
            pass
    assert getattr(exc_info.value, "code", None) == 4401


def test_ws_rejects_role_below_independent_teacher(monkeypatch: pytest.MonkeyPatch) -> None:
    """`ROLE_HIERARCHY` treats teacher/independent_teacher as peers (same level),
    so this specifically tests a role genuinely below the gate, not a school
    `teacher` claim — see the analogous note in test_independent_lecture_wizard.py."""

    async def _below_gate(websocket: Any) -> dict[str, object]:
        return {**TEACHER_CLAIMS, "role": "student"}

    monkeypatch.setattr(ws_voice_router_module, "authenticate_websocket", _below_gate)
    client = TestClient(_make_app())

    with pytest.raises(Exception) as exc_info:
        with client.websocket_connect("/independent/lectures/lec-1/voice"):
            pass
    assert getattr(exc_info.value, "code", None) == 4403


def test_ws_rejects_non_owning_teacher(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _other_teacher(websocket: Any) -> dict[str, object]:
        return {**TEACHER_CLAIMS, "user_id": "teacher-2"}

    monkeypatch.setattr(ws_voice_router_module, "authenticate_websocket", _other_teacher)
    client = TestClient(_make_app())

    with pytest.raises(Exception) as exc_info:
        with client.websocket_connect("/independent/lectures/lec-1/voice"):
            pass
    assert getattr(exc_info.value, "code", None) == 4404


def test_ws_rejects_second_concurrent_session(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _auth(websocket: Any) -> dict[str, object]:
        return dict(TEACHER_CLAIMS)

    async def _conflict(*_a: Any, **_k: Any) -> IndependentLectureVoiceSession:
        raise voice_session_module.VoiceSessionConflictError(
            "voice session in progress in another tab"
        )

    monkeypatch.setattr(ws_voice_router_module, "authenticate_websocket", _auth)
    monkeypatch.setattr(voice_session_module, "open_session", _conflict)
    client = TestClient(_make_app())

    with pytest.raises(Exception) as exc_info:
        with client.websocket_connect("/independent/lectures/lec-1/voice"):
            pass
    assert getattr(exc_info.value, "code", None) == 4409


def test_ws_full_turn_round_trip(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _auth(websocket: Any) -> dict[str, object]:
        return dict(TEACHER_CLAIMS)

    opened = IndependentLectureVoiceSession(
        id="vs-1", lecture_id="lec-1", teacher_user_id="teacher-1"
    )

    async def _open(
        db: Any, *, lecture: Any, teacher_user_id: str
    ) -> IndependentLectureVoiceSession:
        return opened

    closed_sessions: list[Any] = []

    async def _close(db: Any, voice_sess: Any) -> Any:
        closed_sessions.append(voice_sess)
        return voice_sess

    turn = type(
        "Turn",
        (),
        {
            "transcript": "add an example",
            "ai_response_text": "Adding an example.",
            "edit_operation_jsonb": {"op": "append", "text": "An example."},
        },
    )()

    async def _process_turn(db: Any, **kwargs: Any) -> tuple[Any, bytes | None, str | None]:
        return turn, b"tts-audio", None

    monkeypatch.setattr(ws_voice_router_module, "authenticate_websocket", _auth)
    monkeypatch.setattr(voice_session_module, "open_session", _open)
    monkeypatch.setattr(voice_session_module, "close_session", _close)
    monkeypatch.setattr(voice_session_module, "process_turn", _process_turn)

    client = TestClient(_make_app())
    with client.websocket_connect("/independent/lectures/lec-1/voice?language=en") as ws:
        connected = ws.receive_json()
        assert connected["type"] == "connected"
        assert connected["data"]["session_id"] == "vs-1"

        audio_b64 = base64.b64encode(b"chunk-bytes").decode("ascii")
        ws.send_json({"type": "voice_audio_chunk", "data": {"audio_base64": audio_b64}})
        ws.send_json({"type": "voice_turn_end", "data": {}})

        transcript_msg = ws.receive_json()
        assert transcript_msg["type"] == "voice_transcript"
        assert transcript_msg["data"]["transcript"] == "add an example"

        draft_updated = ws.receive_json()
        assert draft_updated["type"] == "lecture_draft_updated"

        audio_msg = ws.receive_json()
        assert audio_msg["type"] == "voice_audio_response"
        assert base64.b64decode(audio_msg["data"]["audio_base64"]) == b"tts-audio"

        ws.send_json({"type": "voice_session_end", "data": {}})

    assert closed_sessions == [opened]


def test_ws_empty_turn_returns_error(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _auth(websocket: Any) -> dict[str, object]:
        return dict(TEACHER_CLAIMS)

    opened = IndependentLectureVoiceSession(
        id="vs-1", lecture_id="lec-1", teacher_user_id="teacher-1"
    )

    async def _open(
        db: Any, *, lecture: Any, teacher_user_id: str
    ) -> IndependentLectureVoiceSession:
        return opened

    async def _close(db: Any, voice_sess: Any) -> Any:
        return voice_sess

    monkeypatch.setattr(ws_voice_router_module, "authenticate_websocket", _auth)
    monkeypatch.setattr(voice_session_module, "open_session", _open)
    monkeypatch.setattr(voice_session_module, "close_session", _close)

    client = TestClient(_make_app())
    with client.websocket_connect("/independent/lectures/lec-1/voice") as ws:
        _connected = ws.receive_json()
        ws.send_json({"type": "voice_turn_end", "data": {}})
        error_msg = ws.receive_json()
        assert error_msg["type"] == "error"
        assert error_msg["data"]["reason"] == "empty_turn"
        ws.send_json({"type": "voice_session_end", "data": {}})
