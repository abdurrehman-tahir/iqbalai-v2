"""Live-feedback WebSocket — T-177 / T-183.

Channel: ``student.live_feedback.{user_id}`` (Flow 6 §3.7).
Mounted at ``/ws/v1/live-feedback``. Ownership: only the authenticated student
may subscribe to their own channel (parent read-only uses REST #72 path).
"""

from __future__ import annotations

import asyncio
import contextlib

import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.middleware import authenticate_websocket
from app.infrastructure.events.consumers.live_feedback import (
    get_active_session,
    live_feedback_channel,
    push_feedback_tick,
    redis_ws_channel,
)
from app.infrastructure.realtime import pubsub as realtime_pubsub
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

router = APIRouter(tags=["live-feedback-ws"])


async def _close_quietly(websocket: WebSocket, code: int) -> None:
    with contextlib.suppress(RuntimeError):
        await websocket.close(code=code)


async def _heartbeat_sender(websocket: WebSocket) -> None:
    while True:
        await asyncio.sleep(HEARTBEAT_INTERVAL_SECONDS)
        await websocket.send_json(build_message(EVENT_HEARTBEAT, {}))


@router.websocket("/live-feedback")
async def live_feedback_ws(websocket: WebSocket) -> None:
    """Owner-only live feedback channel with reconnect-friendly tick resume."""
    claims = await authenticate_websocket(websocket)
    if claims is None:
        await _close_quietly(websocket, 4401)
        return

    user_id = str(claims.get("sub") or "")
    role = str(claims.get("role") or "")
    if not user_id or role not in {"student", "independent_student"}:
        await _close_quietly(websocket, 4403)
        return

    # Optional query override is rejected unless it matches the authed user.
    requested = websocket.query_params.get("user_id")
    if requested and requested != user_id:
        await _close_quietly(websocket, 4403)
        return

    connection_id = await connection_manager.connect(websocket, user_id=user_id)
    channel = live_feedback_channel(user_id)
    heartbeat_task = asyncio.create_task(_heartbeat_sender(websocket))

    try:
        await websocket.send_json(
            build_message(
                EVENT_CONNECTED,
                {"channel": channel, "user_id": user_id},
            )
        )
        # Immediate tick on connect/reconnect if a session is active.
        active = get_active_session(user_id)
        if active is not None:
            tick = await push_feedback_tick(user_id, active)
            await websocket.send_json(build_message("live_feedback_update", tick["payload"]))

        async with realtime_pubsub.subscribe(redis_ws_channel(user_id)) as messages:
            while True:
                try:
                    recv_task = asyncio.create_task(
                        websocket.receive_json(),
                    )
                    msg_task = asyncio.create_task(anext(messages))  # type: ignore[arg-type]
                    done, pending = await asyncio.wait(
                        {recv_task, msg_task},
                        timeout=HEARTBEAT_TIMEOUT_SECONDS,
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                    for t in pending:
                        t.cancel()
                    if not done:
                        await websocket.send_json(
                            build_message(EVENT_ERROR, {"reason": "heartbeat_timeout"})
                        )
                        break
                    if msg_task in done and not msg_task.cancelled():
                        try:
                            inbound = msg_task.result()
                        except StopAsyncIteration:
                            break
                        if isinstance(inbound, dict):
                            payload = inbound.get("payload") or inbound
                            await websocket.send_json(
                                build_message("live_feedback_update", payload)
                            )
                    if recv_task in done and not recv_task.cancelled():
                        with contextlib.suppress(Exception):
                            _ = recv_task.result()
                except WebSocketDisconnect:
                    break
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.warning("live_feedback_ws_error", user_id=user_id, error=str(exc))
        with contextlib.suppress(Exception):
            await websocket.send_json(
                build_message(EVENT_ERROR, {"reason": "internal_error"})
            )
    finally:
        heartbeat_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await heartbeat_task
        await connection_manager.disconnect(connection_id)
        await _close_quietly(websocket, 1000)
