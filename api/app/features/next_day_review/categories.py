"""Known ``teacher_ai_memory.category`` values used by Flow 7 / M-16.

``category`` is a plain String(50) on the M-10 model (intentionally not a
Postgres enum) so M-16 can add values without a migration — T-195 acceptance #4.
"""

from __future__ import annotations

# Persists how a teacher answers the coaching reflective prompt on a review card.
REFLECTIVE_RESPONSE_PATTERN = "reflective_response_pattern"
