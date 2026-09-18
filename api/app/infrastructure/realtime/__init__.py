"""WebSocket connection management + Redis pub/sub fan-out — ARCH §5.12/§9.12/§9.13/§16.9.

T-117 is the first WebSocket feature in the codebase; this package is the
generic transport (connection lifecycle, message envelope, channel fan-out).
Feature-specific buffering (e.g. lecture generation resume) lives with the
feature, not here.
"""

from __future__ import annotations
