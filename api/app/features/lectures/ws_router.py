"""Lecture generation streaming WebSocket — T-117.

Mounted at `/ws/v1/lectures/{lecture_id}/generation` (locked URL pattern,
ARCH §5.12). Auth is the `iqbalai_access` cookie (A-003), not
`Sec-WebSocket-Protocol`.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

import structlog
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import ROLE_HIERARCHY, get_db
from app.core.middleware import authenticate_websocket
from app.features.lectures.generation_stream import get_status, get_tokens_from
from app.features.lectures.repository import LectureRepository
from app.infrastructure.realtime.connection_manager import connection_manager
from app.infrastructure.realtime.pubsub import lecture_channel, subscribe
from app.infrastructure.realtime.schemas import (
    EVENT_CONNECTED,
    EVENT_ERROR,
    EVENT_HEARTBEAT,
    HEARTBEAT_INTERVAL_SECONDS,
    HEARTBEAT_TIMEOUT_SECONDS,
    build_message,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/lectures", tags=["lecture-generation-ws"])


@dataclass
class _StreamState:
    last_sent: int


def _resume_from(websocket: WebSocket) -> int:
    raw = websocket.query_params.get("resume_from", "0")
    try:
        return max(int(raw), 0)
    except ValueError:
        return 0


async def _heartbeat_sender(websocket: WebSocket) -> None:
    """Server → client heartbeat every 30s (§9.14)."""
    while True:
        await asyncio.sleep(HEARTBEAT_INTERVAL_SECONDS)
        await websocket.send_json(build_message(EVENT_HEARTBEAT, {}))


async def _receive_with_timeout(websocket: WebSocket) -> None:
    """Any client message (including heartbeats) resets the 90s idle timer (§9.14)."""
    while True:
        await asyncio.wait_for(websocket.receive_text(), timeout=HEARTBEAT_TIMEOUT_SECONDS)


async def _pump_live_messages(
    websocket: WebSocket, live_messages: AsyncIterator[dict[str, Any]], state: _StreamState
) -> None:
    """Forward pub/sub notices, deduping against anything already sent from backlog."""
    async for msg in live_messages:
        kind = msg.get("kind")
        if kind == "token":
            seq = int(msg.get("seq", 0))
            if seq <= state.last_sent:
                continue  # already covered by the backlog replay
            state.last_sent = seq
            await websocket.send_json(
                build_message(
                    "lecture_generation_token", {"seq": seq, "token": msg.get("token", "")}
                )
            )
        elif kind == "complete":
            await websocket.send_json(
                build_message(
                    "lecture_generation_complete",
                    {
                        "version_id": msg.get("version_id"),
                        "status": msg.get("status", "ready_for_edit"),
                    },
                )
            )
            return
        elif kind == "error":
            await websocket.send_json(
                build_message(EVENT_ERROR, {"reason": msg.get("reason", "generation_failed")})
            )
            return


async def _close_quietly(websocket: WebSocket, code: int) -> None:
    with contextlib.suppress(RuntimeError):
        await websocket.close(code=code)


@router.websocket("/{lecture_id}/generation")
async def lecture_generation_ws(
    websocket: WebSocket,
    lecture_id: str,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Stream lecture generation tokens; `?resume_from=<seq>` replays from that point.

    Access: caller must be the owning teacher, in the lecture's school. Same
    close code for "not found" and "not yours" — a distinct 404 vs 403 would
    leak cross-lecture existence over the channel (mirrors the §3.13 cross-
    tenant denial rule REST endpoints already follow).
    """
    claims = await authenticate_websocket(websocket)
    if claims is None:
        await websocket.close(code=4401)
        return

    role = str(claims.get("role", ""))
    if ROLE_HIERARCHY.get(role, 0) < ROLE_HIERARCHY["teacher"]:
        await websocket.close(code=4403)
        return

    user_id = str(claims.get("user_id", ""))
    school_id = claims.get("school_id")
    lecture = await LectureRepository(db).get_by_id(lecture_id)
    if lecture is None or lecture.school_id != school_id or lecture.teacher_user_id != user_id:
        await websocket.close(code=4404)
        return

    resume_from = _resume_from(websocket)
    connection_id = await connection_manager.connect(websocket, user_id=user_id)

    try:
        async with subscribe(lecture_channel(lecture_id)) as live_messages:
            # Subscribed first, so the backlog read below (however many tokens
            # it returns) is guaranteed at least as fresh as anything the live
            # channel reports (producer RPUSHes before it PUBLISHes) — the
            # count read here IS the seq of the last backlog token, no
            # separate length check needed.
            backlog = await get_tokens_from(lecture_id, resume_from)
            state = _StreamState(last_sent=resume_from)
            for token in backlog:
                state.last_sent += 1
                await websocket.send_json(
                    build_message(
                        "lecture_generation_token",
                        {"seq": state.last_sent, "token": token},
                    )
                )

            status = await get_status(lecture_id)
            if status is not None and status.get("status") == "complete":
                await websocket.send_json(
                    build_message(
                        "lecture_generation_complete",
                        {"version_id": status.get("version_id"), "status": "ready_for_edit"},
                    )
                )
                await _close_quietly(websocket, 1000)
                return
            if status is not None and status.get("status") == "failed":
                await websocket.send_json(
                    build_message(
                        EVENT_ERROR, {"reason": status.get("reason", "generation_failed")}
                    )
                )
                await _close_quietly(websocket, 1011)
                return

            await websocket.send_json(
                build_message(
                    EVENT_CONNECTED, {"heartbeat_interval_seconds": HEARTBEAT_INTERVAL_SECONDS}
                )
            )

            pump = asyncio.create_task(_pump_live_messages(websocket, live_messages, state))
            heartbeat = asyncio.create_task(_heartbeat_sender(websocket))
            receiver = asyncio.create_task(_receive_with_timeout(websocket))
            tasks = {pump, heartbeat, receiver}
            done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)

            if receiver in done and not receiver.cancelled():
                receiver_exc = receiver.exception()
                if isinstance(receiver_exc, asyncio.TimeoutError):
                    logger.info(
                        "lecture_generation_ws_heartbeat_timeout",
                        lecture_id=lecture_id,
                        user_id=user_id,
                    )
                    await _close_quietly(websocket, 1001)
                    return

            await _close_quietly(websocket, 1000)
    except WebSocketDisconnect:
        logger.info("lecture_generation_ws_disconnected", lecture_id=lecture_id, user_id=user_id)
    finally:
        connection_manager.disconnect(connection_id, user_id=user_id)
