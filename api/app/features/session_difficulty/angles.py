"""Teaching-angle cycle for per-session adaptation (T-182)."""

from __future__ import annotations

from typing import Final

# Locked Flow 6 §3.9 angle cycle — do not reorder without an amendment.
TEACHING_ANGLES: Final[tuple[str, ...]] = (
    "example",
    "metaphor",
    "analogy",
    "visual_description",
    "real_world_application",
)


def next_angle(tried_angles: list[str] | None) -> str:
    """Return the next unused angle; wrap only after all five are tried."""
    tried = [a for a in (tried_angles or []) if isinstance(a, str)]
    for angle in TEACHING_ANGLES:
        if angle not in tried:
            return angle
    # Full cycle complete — restart from the beginning for a new pass.
    return TEACHING_ANGLES[0]


def adaptation_context_block(*, angle: str, question_count: int) -> str:
    """STRATEGY block prepended alongside Custom Persona STYLE (ARCH §8.20)."""
    return (
        "ADAPTATION STRATEGY (session-local):\n"
        f"The student has asked {question_count} questions about the same sub-topic "
        "in this session. Try a different teaching angle now: "
        f"**{angle.replace('_', ' ')}**. Do not repeat an angle already used in this "
        "session unless every angle has been exhausted. Preserve any active Custom "
        "Persona style preferences; this block only changes teaching strategy."
    )
