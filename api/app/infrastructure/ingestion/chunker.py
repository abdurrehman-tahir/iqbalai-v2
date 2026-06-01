"""Text chunking — LangChain RecursiveCharacterTextSplitter.

Pre-approved deviation per ARCH §7.7 + docs/DEVIATIONS.md.
Import scope: this file ONLY.  No other file in the codebase may import langchain.
"""

from __future__ import annotations

# Pre-approved deviation: LangChain import limited to this module per ARCH §7.7
from langchain_text_splitters import RecursiveCharacterTextSplitter  # noqa: PLC0415

# Per ARCH §7.7 locked chunking params for reference books
_REFERENCE_BOOK_SPLITTER = RecursiveCharacterTextSplitter(
    chunk_size=1500,
    chunk_overlap=300,
    separators=["\n\n", "\n", ". ", " "],
)


def chunk_text(text: str) -> list[str]:
    """Split *text* into overlapping chunks per ARCH §7.7 reference-book config.

    Returns a list of non-empty chunk strings.
    """
    chunks = _REFERENCE_BOOK_SPLITTER.split_text(text)
    return [c.strip() for c in chunks if c.strip()]
