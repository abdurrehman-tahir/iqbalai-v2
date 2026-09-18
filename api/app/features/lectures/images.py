"""Lecture image insert + AI diagram suggestion helpers (T-132, #30).

Two independent capabilities:
1. ``render_pdf_page_to_png`` — turns one page of an already-ingested
   reference-book PDF into a PNG, for the "accept this diagram" path.
   Uses pdfplumber (STACK_LOCK-locked, "simple typed PDFs only" — the same
   caveat STACK_LOCK already documents, acceptable here since we're
   rendering a whole page snapshot, not extracting structured data).
2. ``suggest_diagrams_from_chunks`` — a single LLM call over the reference
   chunks actually cited by this lecture's first (AI-generated) version,
   asking it to flag chunks whose text reads like it's describing an
   accompanying figure/diagram. No new ingestion pipeline, no vision-LLM
   pass over every page — M-04's ingestion never extracted image/diagram
   metadata (verified: no such column/table exists), so this reuses only
   text already ingested, scoped to books actually used in generation.
"""

from __future__ import annotations

import io
import json
import re
from typing import Any, TypedDict

import structlog

from app.infrastructure.llm.client import chat

logger = structlog.get_logger(__name__)


class IndexedChunk(TypedDict):
    """One reference-book chunk offered to the diagram-suggestion LLM call."""

    index: int
    book_name: str
    page_number: int
    text: str
    library_item_id: str


_JSON_FENCE_RE = re.compile(r"^```(?:json)?|```$", re.MULTILINE)

_SUGGESTION_SYSTEM_PROMPT = """You are helping a teacher find reference-book \
diagrams worth adding to their lecture. You will be given excerpts from \
reference books (each tagged with a book name and page number) and the \
lecture's topic. Identify at most 3 excerpts whose text explicitly reads as \
describing or referring to a diagram, figure, chart, or illustration (e.g. \
"as shown in Figure 3", "the diagram below illustrates", "refer to the \
chart on this page"). Do not guess — only flag excerpts with a clear \
textual signal of an accompanying visual.

Respond with ONLY a JSON array (no prose, no markdown fences), each item:
{"index": <excerpt index>, "reason": "<short reason, one sentence>"}
Return an empty array [] if none qualify."""


class DiagramRenderError(ValueError):
    """The requested PDF page could not be rendered."""


def render_pdf_page_to_png(pdf_bytes: bytes, page_number: int) -> bytes:
    """Render ``page_number`` (1-indexed) of a PDF to a PNG snapshot."""
    import pdfplumber

    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            if page_number < 1 or page_number > len(pdf.pages):
                raise DiagramRenderError(
                    f"Page {page_number} is out of range (book has {len(pdf.pages)} pages)"
                )
            page = pdf.pages[page_number - 1]
            page_image = page.to_image(resolution=150)
            buf = io.BytesIO()
            page_image.original.save(buf, format="PNG")
            return buf.getvalue()
    except DiagramRenderError:
        raise
    except Exception as exc:
        raise DiagramRenderError(f"Could not render page {page_number}: {exc}") from exc


async def suggest_diagrams_from_chunks(
    *, topic: str, chunks: list[IndexedChunk]
) -> list[dict[str, Any]]:
    """One LLM call over pre-fetched reference chunks; returns flagged indices+reasons.

    Caller resolves ``index`` back to (library_item_id, page_number, book_name).
    """
    if not chunks:
        return []

    excerpt_lines = []
    for c in chunks:
        text = str(c["text"])[:600]
        excerpt_lines.append(
            f"[{c['index']}] Book: {c['book_name']} | Page: {c['page_number']}\n{text}"
        )
    user_prompt = f"Lecture topic: {topic}\n\nExcerpts:\n\n" + "\n\n".join(excerpt_lines)

    try:
        raw = await chat(
            [
                {"role": "system", "content": _SUGGESTION_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            task="lecture_generation",
            temperature=0.2,
            max_tokens=500,
        )
        cleaned = _JSON_FENCE_RE.sub("", raw.strip()).strip()
        parsed = json.loads(cleaned)
        if not isinstance(parsed, list):
            return []
        return [item for item in parsed if isinstance(item, dict) and "index" in item]
    except Exception as exc:
        # Best-effort — a suggestion feature must never block the editor.
        logger.warning("diagram_suggestion_failed", error=str(exc))
        return []
