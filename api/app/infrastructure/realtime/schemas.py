"""Locked WS message envelope + lifecycle event types — ARCH §5.12."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

# Server → client lifecycle events (§5.12)
EVENT_CONNECTED = "connected"
EVENT_HEARTBEAT = "heartbeat"
EVENT_ERROR = "error"

# Locked timings — §9.14
HEARTBEAT_INTERVAL_SECONDS = 30
HEARTBEAT_TIMEOUT_SECONDS = 90


def build_message(
    event_type: str,
    data: dict[str, Any],
    *,
    request_id: str | None = None,
) -> dict[str, Any]:
    """Build the locked `{type, id, data, meta}` envelope (§5.12)."""
    return {
        "type": event_type,
        "id": str(uuid.uuid4()),
        "data": data,
        "meta": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "request_id": request_id,
        },
    }
