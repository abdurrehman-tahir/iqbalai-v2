"""T-133 — effort-score formula unit tests.

The `normalize()` basis (30 min / 2000 chars "full effort" caps) is a
flagged, documented assumption — not a locked spec value (see effort.py's
module docstring). These tests pin the *behavior* of the formula given that
basis, so a deliberate change to the caps is visible as a diff here, not a
silent drift.
"""

from __future__ import annotations

from app.features.lectures.effort import (
    ACTIVE_MS_NORMALIZATION_CAP,
    CHAR_DELTA_NORMALIZATION_CAP,
    compute_effort_score,
    normalize,
)


def test_normalize_zero_is_zero() -> None:
    assert normalize(0, 1000) == 0.0


def test_normalize_at_cap_is_one() -> None:
    assert normalize(1000, 1000) == 1.0


def test_normalize_clamps_above_cap() -> None:
    assert normalize(5000, 1000) == 1.0


def test_normalize_negative_clamps_to_zero() -> None:
    assert normalize(-100, 1000) == 0.0


def test_normalize_zero_cap_is_zero_not_divide_by_zero() -> None:
    assert normalize(500, 0) == 0.0


def test_compute_effort_score_zero_effort() -> None:
    assert compute_effort_score(active_ms=0, char_delta=0) == 0.0


def test_compute_effort_score_full_effort_is_one() -> None:
    score = compute_effort_score(
        active_ms=ACTIVE_MS_NORMALIZATION_CAP, char_delta=CHAR_DELTA_NORMALIZATION_CAP
    )
    assert score == 1.0


def test_compute_effort_score_weights_char_delta_more_than_active_ms() -> None:
    """Locked formula: 0.4 * active_ms + 0.6 * char_delta."""
    active_only = compute_effort_score(active_ms=ACTIVE_MS_NORMALIZATION_CAP, char_delta=0)
    chars_only = compute_effort_score(active_ms=0, char_delta=CHAR_DELTA_NORMALIZATION_CAP)
    assert active_only == 0.4
    assert chars_only == 0.6
    assert chars_only > active_only


def test_compute_effort_score_never_exceeds_one_even_over_caps() -> None:
    score = compute_effort_score(active_ms=10**9, char_delta=10**9)
    assert score == 1.0


def test_compute_effort_score_is_rounded() -> None:
    score = compute_effort_score(active_ms=1, char_delta=1)
    assert isinstance(score, float)
    assert len(str(score).split(".")[-1]) <= 4
