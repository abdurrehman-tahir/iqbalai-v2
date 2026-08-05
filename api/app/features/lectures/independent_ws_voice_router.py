"""Voice conversation WebSocket — independent schema (T-125).

Mounted at `/ws/v1/independent/lectures/{lecture_id}/voice` — a distinct
path from the school variant (`/ws/v1/lectures/{lecture_id}/voice`) so the
two never collide at the router level. Mirrors ``ws_voice_router.py``
exactly, scoped to ``Independent*`` models and the ``independent_teacher``
role.
"""

from __future__ import annotations

import asyncio
import base64
import contextlib
from typing import Any

import structlog
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import ROLE_HIERARCHY, get_db
from app.core.middleware import authenticate_websocket
from app.features.lectures import independent_voice_session as voice_session
from app.features.lectures.independent_repository import IndependentLectureRepository
from app.features.lectures.models import IndependentLecture, IndependentLectureVoiceSession
from app.infrastructure.realtime.connection_manager import connection_manager
from app.infrastructure.realtime.schemas import (
    EVENT_CONNECTED,
    EVENT_ERROR,
    EVENT_HEARTBEAT,
    HEARTBEAT_INTERVAL_SECONDS,
    HEARTBEAT_TIMEOUT_SECONDS,
    build_message,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/independent/lectures", tags=["independent-lecture-voice-ws"])

_MAX_TURN_AUDIO_BYTES = 10 * 1024 * 1024


async def _close_quietly(websocket: WebSocket, code: int) -> None:
    with contextlib.suppress(RuntimeError):
        await websocket.close(code=code)


async def _heartbeat_sender(websocket: WebSocket) -> None:
    while True:
        await asyncio.sleep(HEARTBEAT_INTERVAL_SECONDS)
        await websocket.send_json(build_message(EVENT_HEARTBEAT, {}))


async def _process_and_respond(
    websocket: WebSocket,
    db: AsyncSession,
    active_session: IndependentLectureVoiceSession,
    lecture: IndependentLecture,
    audio_bytes: bytes,
    target_language: str,
    *,
    lecture_id: str,
    user_id: str,
) -> None:
    try:
        turn, tts_audio, unavailable_notice = await voice_session.process_turn(
            db,
            voice_session=active_session,
            lecture=lecture,
            audio_bytes=audio_bytes,
            target_language=target_language,
        )
    except Exception as exc:
        logger.error(
            "independent_lecture_voice_turn_failed",
            lecture_id=lecture_id,
            user_id=user_id,
            error=str(exc),
        )
        await websocket.send_json(build_message(EVENT_ERROR, {"reason": "turn_processing_failed"}))
        return

    await websocket.send_json(
        build_message(
            "voice_transcript",
            {"transcript": turn.transcript, "confirmation": turn.ai_response_text},
        )
    )

    edit_op: dict[str, Any] = turn.edit_operation_jsonb or {}
    if edit_op.get("op") not in (None, "none"):
        await websocket.send_json(
            build_message("lecture_draft_updated", {"version_id": lecture.current_version_id})
        )

    if tts_audio is not None:
        await websocket.send_json(
            build_message(
                "voice_audio_response",
                {
                    "audio_base64": base64.b64encode(tts_audio).decode("ascii"),
                    "mime_type": "audio/wav",
                },
            )
        )
    elif unavailable_notice is not None:
        await websocket.send_json(
            build_message("voice_unavailable", {"notice": unavailable_notice})
        )


@router.websocket("/{lecture_id}/voice")
async def independent_lecture_voice_ws(
    websocket: WebSocket,
    lecture_id: str,
    db: AsyncSession = Depends(get_db),
) -> None:
    """ "Talk to AI" during/after lecture creation. `?language=en|ur|sd|ps` (default en)."""
    claims = await authenticate_websocket(websocket)
    if claims is None:
        await websocket.close(code=4401)
        return

    role = str(claims.get("role", ""))
    if ROLE_HIERARCHY.get(role, 0) < ROLE_HIERARCHY["independent_teacher"]:
        await websocket.close(code=4403)
        return

    user_id = str(claims.get("user_id", ""))
    lecture = await IndependentLectureRepository(db).get_by_id(lecture_id)
    if lecture is None or lecture.teacher_user_id != user_id:
        await websocket.close(code=4404)
        return

    try:
        active_session = await voice_session.open_session(
            db, lecture=lecture, teacher_user_id=user_id
        )
    except voice_session.VoiceSessionConflictError:
        await websocket.close(code=4409)
        return

    connection_id = await connection_manager.connect(websocket, user_id=user_id)
    target_language = websocket.query_params.get("language", "en")
    audio_buffer = bytearray()
    heartbeat_task = asyncio.create_task(_heartbeat_sender(websocket))

    try:
        await websocket.send_json(
            build_message(
                EVENT_CONNECTED,
                {
                    "heartbeat_interval_seconds": HEARTBEAT_INTERVAL_SECONDS,
                    "session_id": active_session.id,
                },
            )
        )

        while True:
            raw = await asyncio.wait_for(
                websocket.receive_json(), timeout=HEARTBEAT_TIMEOUT_SECONDS
            )
            msg_type = raw.get("type")
            data: dict[str, Any] = raw.get("data") or {}

            if msg_type == "heartbeat":
                continue
            if msg_type == "voice_session_end":
                break
            if msg_type == "voice_audio_chunk":
                try:
                    chunk = base64.b64decode(str(data.get("audio_base64", "")))
                except (ValueError, TypeError):
                    await websocket.send_json(
                        build_message(EVENT_ERROR, {"reason": "bad_audio_chunk"})
                    )
                    continue
                if len(audio_buffer) + len(chunk) > _MAX_TURN_AUDIO_BYTES:
                    await websocket.send_json(
                        build_message(EVENT_ERROR, {"reason": "turn_audio_too_large"})
                    )
                    audio_buffer.clear()
                    continue
                audio_buffer.extend(chunk)
                continue
            if msg_type == "voice_turn_end":
                if not audio_buffer:
                    await websocket.send_json(build_message(EVENT_ERROR, {"reason": "empty_turn"}))
                    continue
                await _process_and_respond(
                    websocket,
                    db,
                    active_session,
                    lecture,
                    bytes(audio_buffer),
                    target_language,
                    lecture_id=lecture_id,
                    user_id=user_id,
                )
                audio_buffer = bytearray()
                continue

        await _close_quietly(websocket, 1000)
    except WebSocketDisconnect:
        logger.info(
            "independent_lecture_voice_ws_disconnected", lecture_id=lecture_id, user_id=user_id
        )
    except TimeoutError:
        logger.info(
            "independent_lecture_voice_ws_heartbeat_timeout", lecture_id=lecture_id, user_id=user_id
        )
        await _close_quietly(websocket, 1001)
    finally:
        heartbeat_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await heartbeat_task
        connection_manager.disconnect(connection_id, user_id=user_id)
        await voice_session.close_session(db, active_session)
