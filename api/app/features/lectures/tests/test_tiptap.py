"""TipTap JSON -> plain-text extraction tests (T-130)."""

from __future__ import annotations

import pytest

from app.features.lectures.tiptap import (
    InvalidTipTapDocumentError,
    empty_doc,
    extract_plain_text,
)

_SIMPLE_DOC = {
    "type": "doc",
    "content": [
        {"type": "paragraph", "content": [{"type": "text", "text": "Hello world."}]},
        {
            "type": "heading",
            "attrs": {"level": 2},
            "content": [{"type": "text", "text": "Section"}],
        },
        {"type": "paragraph", "content": [{"type": "text", "text": "More text."}]},
    ],
}


def test_extract_plain_text_walks_paragraphs_and_headings() -> None:
    text = extract_plain_text(_SIMPLE_DOC)
    assert "Hello world." in text
    assert "Section" in text
    assert "More text." in text
    # Block nodes introduce breaks — content isn't smashed onto one line.
    assert text.count("\n") >= 2


def test_extract_plain_text_empty_doc_is_empty_string() -> None:
    assert extract_plain_text(empty_doc()) == ""


def test_extract_plain_text_rejects_non_dict() -> None:
    with pytest.raises(InvalidTipTapDocumentError):
        extract_plain_text([])  # type: ignore[arg-type]


def test_extract_plain_text_rejects_wrong_root_type() -> None:
    with pytest.raises(InvalidTipTapDocumentError):
        extract_plain_text({"type": "paragraph", "content": []})


def test_extract_plain_text_rejects_oversized_content() -> None:
    huge = {
        "type": "doc",
        "content": [{"type": "paragraph", "content": [{"type": "text", "text": "x" * 200_001}]}],
    }
    with pytest.raises(InvalidTipTapDocumentError):
        extract_plain_text(huge)


def test_extract_plain_text_handles_nested_list_items() -> None:
    doc = {
        "type": "doc",
        "content": [
            {
                "type": "bulletList",
                "content": [
                    {
                        "type": "listItem",
                        "content": [
                            {
                                "type": "paragraph",
                                "content": [{"type": "text", "text": "Item one"}],
                            }
                        ],
                    }
                ],
            }
        ],
    }
    assert "Item one" in extract_plain_text(doc)
