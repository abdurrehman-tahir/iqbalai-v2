"""Pure highlight-anchoring helpers (T-185, flow-6 §5.5).

Kept free of DB/IO so the "offset no longer maps → drop silently" rule is
unit-testable in isolation.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class Anchor:
    offset: int
    length: int


@dataclass(frozen=True)
class ResolvedMark:
    """Where a persisted highlight lands in the current lecture version."""

    paragraph_id: str
    offset: int
    length: int


def locate_anchor(
    paragraph_text: str, highlighted_text: str, offset_hint: int | None
) -> Anchor | None:
    """Anchor ``highlighted_text`` inside ``paragraph_text`` at creation time.

    The client's offset is trusted only when the span text actually matches;
    otherwise fall back to the first occurrence. ``None`` means the selection
    cannot be anchored (e.g. it spanned paragraphs) — no highlight is stored.
    """
    if not highlighted_text:
        return None
    length = len(highlighted_text)
    if (
        offset_hint is not None
        and offset_hint >= 0
        and paragraph_text[offset_hint : offset_hint + length] == highlighted_text
    ):
        return Anchor(offset=offset_hint, length=length)
    found = paragraph_text.find(highlighted_text)
    if found < 0:
        return None
    return Anchor(offset=found, length=length)


def resolve_mark(
    *,
    paragraph_ordinal: int,
    offset: int,
    length: int,
    highlighted_text: str,
    current_paragraphs: Sequence[tuple[int, str, str]],
) -> ResolvedMark | None:
    """Map a stored anchor onto the current version, or ``None`` to drop it.

    ``current_paragraphs`` is ``(ordinal, paragraph_id, text)``. The mark is
    restored only when the paragraph at the stored ordinal still holds exactly
    the highlighted text at the stored offset — any re-edit that moved or
    removed the span drops the mark silently (§5.5). No fuzzy re-matching: a
    mark on the wrong words is worse than no mark.
    """
    for ordinal, paragraph_id, text in current_paragraphs:
        if ordinal != paragraph_ordinal:
            continue
        if text[offset : offset + length] == highlighted_text:
            return ResolvedMark(paragraph_id=paragraph_id, offset=offset, length=length)
        return None
    return None
