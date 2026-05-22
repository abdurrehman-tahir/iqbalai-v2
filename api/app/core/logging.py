"""Structlog configuration + PII scrubbing."""
from __future__ import annotations

import logging
import re

import structlog

# PII patterns to scrub from log output
_PII_PATTERNS = [
    (re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"), "<email>"),
    (re.compile(r"\b\d{10,13}\b"), "<phone>"),
    (re.compile(r'"password"\s*:\s*"[^"]*"'), '"password": "<redacted>"'),
    (re.compile(r'"token"\s*:\s*"[^"]*"'), '"token": "<redacted>"'),
    (re.compile(r'"secret"\s*:\s*"[^"]*"'), '"secret": "<redacted>"'),
]


def _scrub_pii(
    logger: object, method: str, event_dict: dict[str, object]
) -> dict[str, object]:
    """Remove PII from log events before they are written."""
    message = str(event_dict.get("event", ""))
    for pattern, replacement in _PII_PATTERNS:
        message = pattern.sub(replacement, message)
    event_dict["event"] = message
    return event_dict


def configure_logging(log_level: str = "INFO") -> None:
    """Configure structlog for structured JSON output with PII scrubbing."""
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            _scrub_pii,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelName(log_level)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
