"""Map diagnostic results → Cognitive DNA seed payloads — T-106.

Never encodes grades/scores/percentages — qualitative confidence only.
"""

from __future__ import annotations

from typing import Any

from app.features.diagnostics.schemas import DiagnosticQuestion, FocusAreaRead


def build_topic_confidence(
    *,
    questions: list[DiagnosticQuestion],
    answers: dict[str, Any],
) -> dict[str, object]:
    """Per-topic qualitative confidence for DNA seed (not a grade)."""
    out: dict[str, object] = {}
    for q in questions:
        topic = (q.topic or "").strip() or "this topic"
        raw = answers.get(q.id)
        answered = raw is not None and not (isinstance(raw, str) and not raw.strip())
        # Qualitative labels only — no numeric scores shown to learners.
        level = "building" if answered else "needs_focus"
        prev = out.get(topic)
        if isinstance(prev, dict) and prev.get("level") == "needs_focus" and answered:
            # Keep needs_focus if any item on the topic was unanswered earlier.
            continue
        if isinstance(prev, dict) and prev.get("level") == "building" and not answered:
            out[topic] = {"level": "needs_focus", "answered": False}
            continue
        out[topic] = {"level": level, "answered": answered}
    return out


def focus_areas_to_jsonb(areas: list[FocusAreaRead]) -> list[object]:
    return [a.model_dump() for a in areas]
