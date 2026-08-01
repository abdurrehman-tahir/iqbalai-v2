"""Lecture generation streaming WebSocket tests — T-117.

Uses Starlette's `TestClient.websocket_connect`, not the async REST client —
httpx has no WebSocket support at all, so this is the one legitimate
exception to "async tests use AsyncClient" (that rule guards against the
disposable-engine/cross-loop DB issue, which doesn't apply here since `get_db`
is overridden with a fake session exactly like the REST wizard tests).
"""

from __future__ import annotations

from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from app.core.dependencies import get_db
from app.features.lectures import ws_router as ws_router_module
from app.features.lectures.models import LectureStatus, SchoolLecture

LECTURE = SchoolLecture(
    id="lec-1",
    school_id="school-1",
    teacher_user_id="teacher-1",
    title="Newton's Laws",
    topic="Newton's Laws",
    status=LectureStatus.GENERATING,
)

TEACHER_CLAIMS: dict[str, object] = {
    "sub": "auth-teacher",
    "role": "teacher",
    "user_id": "teacher-1",
    "school_id": "school-1",
}


class _FakeLectureRepo:
    store: dict[str, SchoolLecture] = {LECTURE.id: LECTURE}

    def __init__(self, session: Any) -> None:
        pass

    async def get_by_id(self, lecture_id: str) -> SchoolLecture | None:
        return self.store.get(lecture_id)


async def _fake_db() -> AsyncGenerator[None, None]:
    yield None


@asynccontextmanager
async def _subscribe_yielding(events: list[dict[str, Any]]) -> AsyncIterator[AsyncIterator[dict]]:
    async def _gen() -> AsyncIterator[dict[str, Any]]:
        for event in events:
            yield event

    yield _gen()


@pytest.fixture(autouse=True)
def _patch_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    _FakeLectureRepo.store = {LECTURE.id: LECTURE}
    monkeypatch.setattr(ws_router_module, "LectureRepository", _FakeLectureRepo)


def _make_app() -> FastAPI:
    app = FastAPI()
    app.include_router(ws_router_module.router)
    app.dependency_overrides[get_db] = _fake_db
    return app


def test_ws_rejects_missing_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _no_auth(websocket: Any) -> None:
        return None

    monkeypatch.setattr(ws_router_module, "authenticate_websocket", _no_auth)
    client = TestClient(_make_app())

    with pytest.raises(Exception) as exc_info:
        with client.websocket_connect("/lectures/lec-1/generation"):
            pass
    assert getattr(exc_info.value, "code", None) == 4401


def test_ws_rejects_non_teacher_role(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _student_auth(websocket: Any) -> dict[str, object]:
        return {**TEACHER_CLAIMS, "role": "student"}

    monkeypatch.setattr(ws_router_module, "authenticate_websocket", _student_auth)
    client = TestClient(_make_app())

    with pytest.raises(Exception) as exc_info:
        with client.websocket_connect("/lectures/lec-1/generation"):
            pass
    assert getattr(exc_info.value, "code", None) == 4403


def test_ws_rejects_non_owning_teacher(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _other_teacher_auth(websocket: Any) -> dict[str, object]:
        return {**TEACHER_CLAIMS, "user_id": "teacher-2"}

    monkeypatch.setattr(ws_router_module, "authenticate_websocket", _other_teacher_auth)
    client = TestClient(_make_app())

    with pytest.raises(Exception) as exc_info:
        with client.websocket_connect("/lectures/lec-1/generation"):
            pass
    assert getattr(exc_info.value, "code", None) == 4404


def test_ws_replays_backlog_then_streams_and_completes(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _auth(websocket: Any) -> dict[str, object]:
        return dict(TEACHER_CLAIMS)

    async def _get_tokens_from(lecture_id: str, since_seq: int) -> list[str]:
        assert since_seq == 0
        return ["Newton's ", "first law "]

    async def _get_status(lecture_id: str) -> dict[str, str] | None:
        return None

    monkeypatch.setattr(ws_router_module, "authenticate_websocket", _auth)
    monkeypatch.setattr(ws_router_module, "get_tokens_from", _get_tokens_from)
    monkeypatch.setattr(ws_router_module, "get_status", _get_status)
    monkeypatch.setattr(
        ws_router_module,
        "subscribe",
        lambda channel: _subscribe_yielding(
            [
                {"kind": "token", "seq": 3, "token": "states..."},
                {"kind": "complete", "version_id": "ver-1", "status": "ready_for_edit"},
            ]
        ),
    )

    client = TestClient(_make_app())
    with client.websocket_connect("/lectures/lec-1/generation?resume_from=0") as ws:
        backlog_1 = ws.receive_json()
        backlog_2 = ws.receive_json()
        connected = ws.receive_json()
        live_token = ws.receive_json()
        complete = ws.receive_json()

    assert backlog_1["type"] == "lecture_generation_token"
    assert backlog_1["data"] == {"seq": 1, "token": "Newton's "}
    assert backlog_2["data"] == {"seq": 2, "token": "first law "}
    assert connected["type"] == "connected"
    assert connected["data"]["heartbeat_interval_seconds"] == 30
    assert live_token["data"] == {"seq": 3, "token": "states..."}
    assert complete["type"] == "lecture_generation_complete"
    assert complete["data"] == {"version_id": "ver-1", "status": "ready_for_edit"}


def test_ws_resume_from_seq_skips_already_seen_tokens(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _auth(websocket: Any) -> dict[str, object]:
        return dict(TEACHER_CLAIMS)

    async def _get_tokens_from(lecture_id: str, since_seq: int) -> list[str]:
        assert since_seq == 2
        return ["states "]

    async def _get_status(lecture_id: str) -> dict[str, str] | None:
        return None

    monkeypatch.setattr(ws_router_module, "authenticate_websocket", _auth)
    monkeypatch.setattr(ws_router_module, "get_tokens_from", _get_tokens_from)
    monkeypatch.setattr(ws_router_module, "get_status", _get_status)
    monkeypatch.setattr(
        ws_router_module,
        "subscribe",
        lambda channel: _subscribe_yielding(
            [
                # Already covered by backlog (seq 3) — must be skipped, not re-sent.
                {"kind": "token", "seq": 3, "token": "states "},
                {"kind": "complete", "version_id": "ver-1", "status": "ready_for_edit"},
            ]
        ),
    )

    client = TestClient(_make_app())
    with client.websocket_connect("/lectures/lec-1/generation?resume_from=2") as ws:
        backlog = ws.receive_json()
        connected = ws.receive_json()
        complete = ws.receive_json()

    assert backlog["data"] == {"seq": 3, "token": "states "}
    assert connected["type"] == "connected"
    assert complete["type"] == "lecture_generation_complete"


def test_ws_already_complete_replays_then_closes(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _auth(websocket: Any) -> dict[str, object]:
        return dict(TEACHER_CLAIMS)

    async def _get_tokens_from(lecture_id: str, since_seq: int) -> list[str]:
        return []

    async def _get_status(lecture_id: str) -> dict[str, str] | None:
        return {"status": "complete", "version_id": "ver-1"}

    monkeypatch.setattr(ws_router_module, "authenticate_websocket", _auth)
    monkeypatch.setattr(ws_router_module, "get_tokens_from", _get_tokens_from)
    monkeypatch.setattr(ws_router_module, "get_status", _get_status)
    monkeypatch.setattr(ws_router_module, "subscribe", lambda channel: _subscribe_yielding([]))

    client = TestClient(_make_app())
    with client.websocket_connect("/lectures/lec-1/generation") as ws:
        complete = ws.receive_json()

    assert complete["type"] == "lecture_generation_complete"
    assert complete["data"] == {"version_id": "ver-1", "status": "ready_for_edit"}
