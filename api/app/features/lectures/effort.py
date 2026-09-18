"""Edit-effort scoring (T-133, Flow 5 §3.5 #31).

Locked formula: ``effort_score = normalize(active_ms) * 0.4 + normalize(char_delta) * 0.6``.

**Flagged gap, not silently guessed:** the spec (flow-5 §3.5) locks this
formula but never defines what "normalize" normalizes *against* — no cap,
percentile, or fixed max is stated anywhere in §3.5 or the adjoining §3.6
scoring section. Absent that, this module uses documented, easily-tunable
min-max caps (below) clamped to ``[0, 1]`` — a "full effort" reference
session, not a statistical percentile (no population data exists yet to
percentile against). This is a product decision T-134/Hamby/Abd should
confirm or override, not an architectural fact; flagged in the T-133
backlog entry and PR description rather than asserted as locked.

``active_ms``/``char_delta`` themselves (the acceptance-critical raw inputs
to T-134's scoring pipeline) are unaffected by this gap — they are recorded
exactly as measured, independent of how they're later normalized.
"""

from __future__ import annotations

# "Full effort" reference points — NOT a locked spec value (see module
# docstring). 30 minutes of active editing / 2000 characters changed each
# count as "full" (1.0) on their respective axis.
ACTIVE_MS_NORMALIZATION_CAP = 30 * 60 * 1000
CHAR_DELTA_NORMALIZATION_CAP = 2000

_ACTIVE_MS_WEIGHT = 0.4
_CHAR_DELTA_WEIGHT = 0.6


def normalize(value: int, cap: int) -> float:
    """Min-max normalize to [0, 1], clamped — never negative, never > 1."""
    if cap <= 0:
        return 0.0
    return min(max(value, 0) / cap, 1.0)


def compute_effort_score(*, active_ms: int, char_delta: int) -> float:
    """The locked formula, rounded to 4 decimal places for stable storage/tests."""
    score = (
        normalize(active_ms, ACTIVE_MS_NORMALIZATION_CAP) * _ACTIVE_MS_WEIGHT
        + normalize(char_delta, CHAR_DELTA_NORMALIZATION_CAP) * _CHAR_DELTA_WEIGHT
    )
    return round(score, 4)
