"""ConnectionManager unit tests — T-117."""

from __future__ import annotations

from typing import Any

import pytest

from app.infrastructure.realtime.connection_manager import ConnectionManager


class _FakeWebSocket:
    def __init__(self) -> None:
        self.accepted = False
        self.sent: list[dict[str, Any]] = []

    async def accept(self) -> None:
        self.accepted = True

    async def send_json(self, message: dict[str, Any]) -> None:
        self.sent.append(message)


@pytest.mark.asyncio
async def test_connect_accepts_and_registers() -> None:
    manager = ConnectionManager()
    ws = _FakeWebSocket()

    connection_id = await manager.connect(ws, user_id="user-1")  # type: ignore[arg-type]

    assert ws.accepted is True
    assert manager.is_connected("user-1") is True
    assert connection_id


@pytest.mark.asyncio
async def test_send_delivers_to_registered_connection() -> None:
    manager = ConnectionManager()
    ws = _FakeWebSocket()
    connection_id = await manager.connect(ws, user_id="user-1")  # type: ignore[arg-type]

    delivered = await manager.send(connection_id, {"type": "heartbeat"})

    assert delivered is True
    assert ws.sent == [{"type": "heartbeat"}]


@pytest.mark.asyncio
async def test_send_to_unknown_connection_returns_false() -> None:
    manager = ConnectionManager()

    delivered = await manager.send("unknown-id", {"type": "heartbeat"})

    assert delivered is False


@pytest.mark.asyncio
async def test_disconnect_removes_connection_and_user_index() -> None:
    manager = ConnectionManager()
    ws = _FakeWebSocket()
    connection_id = await manager.connect(ws, user_id="user-1")  # type: ignore[arg-type]

    manager.disconnect(connection_id, user_id="user-1")

    assert manager.is_connected("user-1") is False
    assert await manager.send(connection_id, {"type": "heartbeat"}) is False


@pytest.mark.asyncio
async def test_multiple_connections_same_user_survive_partial_disconnect() -> None:
    manager = ConnectionManager()
    ws_a, ws_b = _FakeWebSocket(), _FakeWebSocket()
    id_a = await manager.connect(ws_a, user_id="user-1")  # type: ignore[arg-type]
    await manager.connect(ws_b, user_id="user-1")  # type: ignore[arg-type]

    manager.disconnect(id_a, user_id="user-1")

    assert manager.is_connected("user-1") is True
