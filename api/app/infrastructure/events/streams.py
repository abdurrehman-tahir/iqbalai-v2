"""JetStream stream ensure helpers — ARCH §9.4 / T-173.

Uses the three locked streams. ``student-events`` captures ``student.>``
(including ``student.lecture.*``). Retention follows ARCH §9.4 (30 days),
not the Flow-6 narrative "7 days" — ARCH is authoritative.
"""

from __future__ import annotations

from typing import Any

import structlog

from app.infrastructure.events.subjects import (
    CONTENT_EVENTS_STREAM,
    STUDENT_EVENTS_STREAM,
    SYSTEM_EVENTS_STREAM,
)

logger = structlog.get_logger(__name__)

# ARCH §9.4 locked params (seconds / bytes).
_DAY = 24 * 60 * 60
STUDENT_MAX_AGE_SECONDS = 30 * _DAY
CONTENT_MAX_AGE_SECONDS = 90 * _DAY
SYSTEM_MAX_AGE_SECONDS = 90 * _DAY
STUDENT_MAX_BYTES = 50_000_000_000
CONTENT_MAX_BYTES = 50_000_000_000
SYSTEM_MAX_BYTES = 20_000_000_000

_STREAM_SPECS: tuple[dict[str, Any], ...] = (
    {
        "name": STUDENT_EVENTS_STREAM,
        "subjects": ["student.>"],
        "max_age": STUDENT_MAX_AGE_SECONDS,
        "max_bytes": STUDENT_MAX_BYTES,
    },
    {
        "name": CONTENT_EVENTS_STREAM,
        "subjects": ["lecture.>", "lesson.>", "curriculum.>", "teacher.>"],
        "max_age": CONTENT_MAX_AGE_SECONDS,
        "max_bytes": CONTENT_MAX_BYTES,
    },
    {
        "name": SYSTEM_EVENTS_STREAM,
        "subjects": ["system.>", "prediction.>", "parent.>", "va.>"],
        "max_age": SYSTEM_MAX_AGE_SECONDS,
        "max_bytes": SYSTEM_MAX_BYTES,
    },
)


async def ensure_streams(js: Any) -> None:
    """Idempotently create the three locked JetStream streams."""
    from nats.js.api import DiscardPolicy, RetentionPolicy, StorageType, StreamConfig

    for spec in _STREAM_SPECS:
        cfg = StreamConfig(
            name=spec["name"],
            subjects=list(spec["subjects"]),
            retention=RetentionPolicy.LIMITS,
            max_age=spec["max_age"],
            max_bytes=spec["max_bytes"],
            storage=StorageType.FILE,
            discard=DiscardPolicy.OLD,
            num_replicas=1,
        )
        try:
            await js.add_stream(cfg)
            logger.info("nats_stream_created", stream=spec["name"])
        except Exception as exc:
            # Stream already exists — update retention/subjects if the server allows.
            msg = str(exc).lower()
            if "already in use" in msg or "exist" in msg or "10058" in msg:
                try:
                    await js.update_stream(cfg)
                    logger.info("nats_stream_updated", stream=spec["name"])
                except Exception as update_exc:
                    logger.debug(
                        "nats_stream_ensure_noop",
                        stream=spec["name"],
                        error=str(update_exc),
                    )
            else:
                logger.warning(
                    "nats_stream_ensure_failed",
                    stream=spec["name"],
                    error=str(exc),
                )
                raise
