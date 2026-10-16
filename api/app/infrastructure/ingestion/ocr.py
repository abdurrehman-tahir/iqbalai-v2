"""OCR routing — PaddleOCR primary, Tesseract 5 fallback (ARCH §11.11 / STACK_LOCK §4.3).

Lazy imports so unit tests can monkeypatch without installing heavy OCR wheels.
"""

from __future__ import annotations

from typing import Literal

import structlog

logger = structlog.get_logger(__name__)

ExtractionMethod = Literal["paddleocr", "tesseract"]


class OcrUnavailableError(RuntimeError):
    """Neither PaddleOCR nor Tesseract could produce text."""


def _paddle_ocr(data: bytes) -> str | None:
    try:
        from paddleocr import PaddleOCR
    except Exception as exc:  # noqa: BLE001 — missing optional dep is expected in CI
        logger.info("paddleocr_unavailable", error=str(exc))
        return None
    try:
        import io

        from PIL import Image

        img = Image.open(io.BytesIO(data))
        ocr = PaddleOCR(use_angle_cls=True, lang="en", show_log=False)
        result = ocr.ocr(img, cls=True)
        lines: list[str] = []
        if not result:
            return ""
        for block in result:
            if not block:
                continue
            for line in block:
                if line and len(line) >= 2 and line[1]:
                    text = line[1][0]
                    if isinstance(text, str) and text.strip():
                        lines.append(text.strip())
        return "\n".join(lines)
    except Exception as exc:  # noqa: BLE001
        logger.warning("paddleocr_failed", error=str(exc))
        return None


def _tesseract_ocr(data: bytes) -> str | None:
    try:
        import io

        import pytesseract
        from PIL import Image
    except Exception as exc:  # noqa: BLE001
        logger.info("tesseract_unavailable", error=str(exc))
        return None
    try:
        img = Image.open(io.BytesIO(data))
        # en+ur when tessdata packs are present; eng alone still works for typed text.
        text = pytesseract.image_to_string(img, lang="eng")
        return (text or "").strip()
    except Exception as exc:  # noqa: BLE001
        logger.warning("tesseract_failed", error=str(exc))
        return None


def extract_text_from_image(data: bytes) -> tuple[str, ExtractionMethod]:
    """Run OCR on image bytes. Returns (text, extraction_method).

    Raises OcrUnavailableError when both backends fail or return empty.
    """
    paddle = _paddle_ocr(data)
    if paddle is not None and paddle.strip():
        logger.info("ocr_ok", method="paddleocr", chars=len(paddle))
        return paddle.strip(), "paddleocr"

    tess = _tesseract_ocr(data)
    if tess is not None and tess.strip():
        logger.info("ocr_ok", method="tesseract", chars=len(tess))
        return tess.strip(), "tesseract"

    raise OcrUnavailableError(
        "OCR failed — PaddleOCR and Tesseract produced no text for this image"
    )
