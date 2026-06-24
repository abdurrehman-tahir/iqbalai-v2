"""Shared LLM types — ARCH §8.6."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PromptCall:
    """Rendered prompt ready for the LLM client."""

    version: str
    system: str
    user: str
    temperature: float = 0.7
    max_tokens: int = 2048
