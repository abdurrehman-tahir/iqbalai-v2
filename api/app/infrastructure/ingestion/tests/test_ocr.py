"""T-212 — OCR routing unit tests (mocked backends)."""

from __future__ import annotations

import pytest

from app.infrastructure.ingestion.ocr import (
    OcrUnavailableError,
    extract_text_from_image,
)


def test_paddle_preferred(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.infrastructure.ingestion.ocr._paddle_ocr",
        lambda _data: "paddle text",
    )
    monkeypatch.setattr(
        "app.infrastructure.ingestion.ocr._tesseract_ocr",
        lambda _data: "tess text",
    )
    text, method = extract_text_from_image(b"fake")
    assert text == "paddle text"
    assert method == "paddleocr"


def test_tesseract_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.infrastructure.ingestion.ocr._paddle_ocr",
        lambda _data: None,
    )
    monkeypatch.setattr(
        "app.infrastructure.ingestion.ocr._tesseract_ocr",
        lambda _data: "tess only",
    )
    text, method = extract_text_from_image(b"fake")
    assert method == "tesseract"
    assert text == "tess only"


def test_both_fail(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.infrastructure.ingestion.ocr._paddle_ocr",
        lambda _data: None,
    )
    monkeypatch.setattr(
        "app.infrastructure.ingestion.ocr._tesseract_ocr",
        lambda _data: "",
    )
    with pytest.raises(OcrUnavailableError):
        extract_text_from_image(b"fake")
