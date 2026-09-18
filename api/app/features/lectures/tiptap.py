"""TipTap/ProseMirror JSON document helpers (T-130, STACK_LOCK §2).

TipTap is the locked rich-text editor. Its ``editor.getJSON()`` output is
stored verbatim in ``lecture_versions.content_jsonb`` (source of truth for
the editor). ``lecture_versions.body`` stays a plain-text extraction of that
same document — existing scoring/embedding/RAG code paths operate on text,
not ProseMirror JSON, and T-134/T-135/T-136 need a stable plain-text view to
diff and embed.
"""

from __future__ import annotations

from typing import Any

# Node types that introduce a paragraph break when walking the doc tree.
_BLOCK_BREAK_TYPES = frozenset(
    {"paragraph", "heading", "listItem", "blockquote", "codeBlock", "horizontalRule"}
)

_MAX_CONTENT_CHARS = 200_000


class InvalidTipTapDocumentError(ValueError):
    """Raised when a payload is not a well-formed TipTap/ProseMirror document."""


def extract_plain_text(doc: dict[str, Any]) -> str:
    """Depth-first walk of a TipTap JSON doc, concatenating ``text`` leaves.

    Raises ``InvalidTipTapDocumentError`` on a non-dict root or a root whose
    ``type`` isn't ``"doc"`` — callers should surface this as a 422, not a 500.
    """
    if not isinstance(doc, dict):
        raise InvalidTipTapDocumentError("content_jsonb must be a JSON object")
    if doc.get("type") != "doc":
        raise InvalidTipTapDocumentError("content_jsonb root node must have type 'doc'")

    parts: list[str] = []

    def walk(node: dict[str, Any]) -> None:
        if not isinstance(node, dict):
            return
        if node.get("type") == "text":
            parts.append(str(node.get("text", "")))
        for child in node.get("content", None) or []:
            walk(child)
        if node.get("type") in _BLOCK_BREAK_TYPES:
            parts.append("\n")

    walk(doc)
    text = "".join(parts).strip()
    if len(text) > _MAX_CONTENT_CHARS:
        raise InvalidTipTapDocumentError(
            f"Lecture content exceeds the {_MAX_CONTENT_CHARS}-character limit"
        )
    return text


def empty_doc() -> dict[str, Any]:
    """A minimal valid empty TipTap document, for tests/fixtures."""
    return {"type": "doc", "content": [{"type": "paragraph", "content": []}]}
