"""In-memory per-container WebSocket registry — ARCH §9.13/§16.9.

State here is local to this API process; cross-container delivery is Redis
pub/sub (`pubsub.py`), not this registry. `ConnectionManager` exists so a
feature can look up "is this user connected right now" without owning
WebSocket bookkeeping itself.
"""

from __future__ import annotations

import uuid
from typing import Any

import structlog
from starlette.websockets import WebSocket

logger = structlog.get_logger(__name__)


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[str, WebSocket] = {}
        self._user_index: dict[str, set[str]] = {}

    async def connect(self, websocket: WebSocket, *, user_id: str) -> str:
        """Accept the WS handshake and register the connection. Returns connection_id."""
        await websocket.accept()
        connection_id = str(uuid.uuid4())
        self._connections[connection_id] = websocket
        self._user_index.setdefault(user_id, set()).add(connection_id)
        logger.info("ws_connected", connection_id=connection_id, user_id=user_id)
        return connection_id

    def disconnect(self, connection_id: str, *, user_id: str) -> None:
        """Clean up local state. Does not close the socket (caller already did)."""
        self._connections.pop(connection_id, None)
        ids = self._user_index.get(user_id)
        if ids is not None:
            ids.discard(connection_id)
            if not ids:
                self._user_index.pop(user_id, None)
        logger.info("ws_disconnected", connection_id=connection_id, user_id=user_id)

    async def send(self, connection_id: str, message: dict[str, Any]) -> bool:
        """Send a message to a locally-held connection. False if not found here."""
        websocket = self._connections.get(connection_id)
        if websocket is None:
            return False
        await websocket.send_json(message)
        return True

    def is_connected(self, user_id: str) -> bool:
        return bool(self._user_index.get(user_id))


# Process-wide singleton — one per API container, matching §16.9's per-container model.
connection_manager = ConnectionManager()
