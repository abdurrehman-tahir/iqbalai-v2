"""PDF text extraction — pdfplumber lightweight fallback (STACK_LOCK §4.3).

MinerU (deep-learning, full tables/equations) is the primary extractor for production;
pdfplumber handles simple typed PDFs at launch.  When MinerU is available in the
deployment environment, swap `extract_text_from_pdf` to call MinerU and fall back here.
"""

from __future__ import annotations

import structlog
from io import BytesIO

logger = structlog.get_logger(__name__)


def extract_text_from_pdf(data: bytes) -> list[dict[str, object]]:
    """Extract per-page text from a PDF byte string using pdfplumber.

    Returns a list of dicts with ``page`` (1-indexed) and ``text`` keys.
    Raises ``ValueError`` if the PDF has no extractable text (image-only PDF
    that requires OCR — OCR pipeline deferred to TODO.md).
    """
    import pdfplumber  # local import so the dep is optional at import time

    pages: list[dict[str, object]] = []
    with pdfplumber.open(BytesIO(data)) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            pages.append({"page": i, "text": text.strip()})

    non_empty = [p for p in pages if p["text"]]
    if not non_empty:
        raise ValueError(
            "No extractable text found in PDF. "
            "Image-only PDFs require OCR (PaddleOCR) — deferred to TODO.md."
        )

    logger.info("pdf_extracted", total_pages=len(pages), non_empty_pages=len(non_empty))
    return pages
