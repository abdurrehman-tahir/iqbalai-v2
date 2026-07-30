"""Derive coaching focus areas from a completed diagnostic — T-105.

Never computes scores, percentages, or pass/fail. Unanswered / timed-out items
become coaching suggestions only (Flow 4 §3.6).
"""

from __future__ import annotations

from typing import Any

from app.features.diagnostics.schemas import DiagnosticQuestion, FocusAreaRead

_DEFAULT_TOPIC = "this topic"
_MAX_FOCUS = 8


def derive_focus_areas(
    *,
    questions: list[DiagnosticQuestion],
    answers: dict[str, Any],
    timed_out: bool = False,
) -> tuple[list[FocusAreaRead], str]:
    """Return (focus_areas, coaching_summary) with no grade language."""
    unanswered: list[DiagnosticQuestion] = []
    for q in questions:
        raw = answers.get(q.id)
        if raw is None or (isinstance(raw, str) and not raw.strip()):
            unanswered.append(q)

    areas: list[FocusAreaRead] = []
    seen: set[str] = set()

    for q in unanswered:
        topic = (q.topic or "").strip() or _DEFAULT_TOPIC
        key = topic.casefold()
        if key in seen:
            continue
        seen.add(key)
        if timed_out:
            suggestion = f"Spend more time on {topic} — you can return when you're ready."
        else:
            suggestion = f"Spend more time on {topic}."
        areas.append(FocusAreaRead(topic=topic, suggestion=suggestion))
        if len(areas) >= _MAX_FOCUS:
            break

    if not areas:
        # All answered: still coach, never score — highlight unique topics as practice focus.
        for q in questions:
            topic = (q.topic or "").strip() or _DEFAULT_TOPIC
            key = topic.casefold()
            if key in seen:
                continue
            seen.add(key)
            areas.append(
                FocusAreaRead(
                    topic=topic,
                    suggestion=f"Keep practicing {topic} to build confidence.",
                )
            )
            if len(areas) >= min(5, _MAX_FOCUS):
                break

    if timed_out:
        summary = (
            "Time ran out, so we saved your progress. Here are areas to focus on next — "
            "this is coaching guidance, not a mark or score."
        )
    elif unanswered:
        summary = (
            "Nice work finishing what you could. Here are areas to focus on — "
            "coaching guidance only, never marks."
        )
    else:
        summary = (
            "You completed every question. Keep strengthening these areas — "
            "this is coaching guidance, not a mark or score."
        )

    return areas, summary
