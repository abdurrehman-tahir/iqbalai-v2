"""Auto-derived ``lecture_versions.edit_summary`` annotations (T-130, #29-#31).

Set once at save time, never touched by the async scoring pipeline (see the
``edit_summary`` column docstring in ``models.py``). T-131 (voice) and T-132
(image) append their own annotation via ``extra_annotations`` — this module
only owns the generic text-delta heuristic.
"""

from __future__ import annotations

_SUBSTANTIAL_REWRITE_CHARS = 200


def derive_edit_summary(
    *,
    previous_body: str | None,
    new_body: str,
    extra_annotations: list[str] | None = None,
) -> list[str] | None:
    """Best-effort human-readable annotations for the version timeline (T-137).

    ``previous_body`` is ``None`` for the very first version (nothing to diff
    against — no annotation). Returns ``None`` (not ``[]``) when there is
    nothing to say, matching the column's nullable JSONB shape.
    """
    annotations: list[str] = list(extra_annotations or [])

    if previous_body is not None:
        delta = len(new_body) - len(previous_body)
        if new_body == previous_body:
            pass
        elif abs(delta) >= _SUBSTANTIAL_REWRITE_CHARS:
            annotations.append("Substantial rewrite")
        elif delta > 0:
            annotations.append("Added content")
        elif delta < 0:
            annotations.append("Trimmed content")
        else:
            annotations.append("Edited content")

    return annotations or None
