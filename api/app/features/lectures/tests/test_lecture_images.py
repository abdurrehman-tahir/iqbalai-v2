"""T-132 — images.py unit tests: PDF page rendering + diagram-suggestion LLM call."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.features.lectures.images import (
    DiagramRenderError,
    render_pdf_page_to_png,
    suggest_diagrams_from_chunks,
)


def test_render_pdf_page_to_png_rejects_out_of_range_page() -> None:
    fake_pdf = MagicMock()
    fake_pdf.pages = [MagicMock()]
    fake_pdf.__enter__ = MagicMock(return_value=fake_pdf)
    fake_pdf.__exit__ = MagicMock(return_value=False)

    with patch("pdfplumber.open", return_value=fake_pdf):
        with pytest.raises(DiagramRenderError, match="out of range"):
            render_pdf_page_to_png(b"%PDF-fake", page_number=5)


def test_render_pdf_page_to_png_rejects_page_zero() -> None:
    fake_pdf = MagicMock()
    fake_pdf.pages = [MagicMock()]
    fake_pdf.__enter__ = MagicMock(return_value=fake_pdf)
    fake_pdf.__exit__ = MagicMock(return_value=False)

    with patch("pdfplumber.open", return_value=fake_pdf):
        with pytest.raises(DiagramRenderError):
            render_pdf_page_to_png(b"%PDF-fake", page_number=0)


def test_render_pdf_page_to_png_success() -> None:
    fake_page = MagicMock()
    fake_image = MagicMock()

    def _fake_save(buf: object, format: str) -> None:
        buf.write(b"\x89PNG\r\n\x1a\nfakepngdata")  # type: ignore[attr-defined]

    fake_image.original.save.side_effect = _fake_save
    fake_page.to_image.return_value = fake_image

    fake_pdf = MagicMock()
    fake_pdf.pages = [fake_page]
    fake_pdf.__enter__ = MagicMock(return_value=fake_pdf)
    fake_pdf.__exit__ = MagicMock(return_value=False)

    with patch("pdfplumber.open", return_value=fake_pdf):
        png = render_pdf_page_to_png(b"%PDF-fake", page_number=1)

    assert png.startswith(b"\x89PNG")
    fake_page.to_image.assert_called_once_with(resolution=150)


def test_render_pdf_page_to_png_wraps_unexpected_errors() -> None:
    with patch("pdfplumber.open", side_effect=RuntimeError("corrupt file")):
        with pytest.raises(DiagramRenderError, match="Could not render page"):
            render_pdf_page_to_png(b"not a pdf", page_number=1)


@pytest.mark.asyncio
async def test_suggest_diagrams_from_chunks_empty_input_short_circuits() -> None:
    result = await suggest_diagrams_from_chunks(topic="Newton's Laws", chunks=[])
    assert result == []


@pytest.mark.asyncio
async def test_suggest_diagrams_from_chunks_parses_llm_json() -> None:
    chunks = [
        {"index": 0, "book_name": "Physics 101", "page_number": 12, "text": "plain text"},
        {
            "index": 1,
            "book_name": "Physics 101",
            "page_number": 34,
            "text": "As shown in Figure 3, the forces balance.",
        },
    ]
    with patch(
        "app.features.lectures.images.chat",
        return_value='[{"index": 1, "reason": "Mentions Figure 3"}]',
    ):
        result = await suggest_diagrams_from_chunks(topic="Forces", chunks=chunks)

    assert result == [{"index": 1, "reason": "Mentions Figure 3"}]


@pytest.mark.asyncio
async def test_suggest_diagrams_from_chunks_handles_markdown_fenced_json() -> None:
    chunks = [{"index": 0, "book_name": "B", "page_number": 1, "text": "t"}]
    with patch(
        "app.features.lectures.images.chat",
        return_value='```json\n[{"index": 0, "reason": "r"}]\n```',
    ):
        result = await suggest_diagrams_from_chunks(topic="T", chunks=chunks)
    assert result == [{"index": 0, "reason": "r"}]


@pytest.mark.asyncio
async def test_suggest_diagrams_from_chunks_never_raises_on_llm_failure() -> None:
    chunks = [{"index": 0, "book_name": "B", "page_number": 1, "text": "t"}]
    with patch("app.features.lectures.images.chat", side_effect=RuntimeError("LLM down")):
        result = await suggest_diagrams_from_chunks(topic="T", chunks=chunks)
    assert result == []


@pytest.mark.asyncio
async def test_suggest_diagrams_from_chunks_ignores_non_list_response() -> None:
    chunks = [{"index": 0, "book_name": "B", "page_number": 1, "text": "t"}]
    with patch("app.features.lectures.images.chat", return_value='{"not": "a list"}'):
        result = await suggest_diagrams_from_chunks(topic="T", chunks=chunks)
    assert result == []
