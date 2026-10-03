/**
 * Yellow-mark segmentation for persisted highlights (T-185, flow-6 §3.6/§5.5).
 *
 * The server already re-verifies every anchor against the current lecture
 * version and nulls `mark` when the span no longer maps — here we only split a
 * paragraph's text into plain / marked runs. Overlapping or out-of-range marks
 * are skipped (defensive: a bad mark must never break the lecture text).
 */
import type { StudentHighlightRead } from "@/lib/api";

export type TextSegment = { text: string; highlightId: string | null };

export function marksByParagraph(
  highlights: StudentHighlightRead[],
): Map<string, { id: string; offset: number; length: number }[]> {
  const out = new Map<
    string,
    { id: string; offset: number; length: number }[]
  >();
  for (const h of highlights) {
    if (!h.mark) continue;
    const list = out.get(h.mark.paragraph_id) ?? [];
    list.push({ id: h.id, offset: h.mark.offset, length: h.mark.length });
    out.set(h.mark.paragraph_id, list);
  }
  return out;
}

export function segmentParagraph(
  text: string,
  marks: { id: string; offset: number; length: number }[],
): TextSegment[] {
  const sorted = [...marks].sort((a, b) => a.offset - b.offset);
  const segments: TextSegment[] = [];
  let cursor = 0;
  for (const mark of sorted) {
    const end = mark.offset + mark.length;
    if (mark.length <= 0 || mark.offset < cursor || end > text.length) continue;
    if (mark.offset > cursor) {
      segments.push({
        text: text.slice(cursor, mark.offset),
        highlightId: null,
      });
    }
    segments.push({ text: text.slice(mark.offset, end), highlightId: mark.id });
    cursor = end;
  }
  if (cursor < text.length || segments.length === 0) {
    segments.push({ text: text.slice(cursor), highlightId: null });
  }
  return segments;
}

/** Character offset of the current selection start inside `container`'s text. */
export function selectionOffsetWithin(
  container: Node,
  range: Range,
): number | null {
  if (!container.contains(range.startContainer)) return null;
  const pre = document.createRange();
  pre.selectNodeContents(container);
  pre.setEnd(range.startContainer, range.startOffset);
  return pre.toString().length;
}
