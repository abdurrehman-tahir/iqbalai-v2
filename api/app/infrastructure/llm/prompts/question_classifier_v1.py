"""Question classification typed prompt — T-157 (Flow 6 §3.3 / ARCH §8.6).

Classifies a student lecture question as ``misconception`` (wrong mental model)
or ``knowledge_gap`` (never learned). Baseline only; Flow 9 Phase 5 refines
with Cognitive DNA training data.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.infrastructure.llm.types import PromptCall

PROMPT_VERSION = "question_classifier.v1"


class QuestionClassifierInput(BaseModel):
    question_text: str = Field(min_length=1, max_length=4000)
    highlight_text: str | None = Field(default=None, max_length=4000)
    lecture_excerpt: str = Field(default="", max_length=8000)
    target_language: Literal["en", "ur", "sd", "ps"] = "en"


class QuestionClassifierOutput(BaseModel):
    classification: Literal["misconception", "knowledge_gap"]
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    rationale: str = Field(default="", max_length=1000)


SYSTEM = """You classify secondary-school student questions asked while studying a lecture.

Return ONLY valid JSON:
{{
  "classification": "misconception" | "knowledge_gap",
  "confidence": 0.0-1.0,
  "rationale": "brief reason"
}}

Definitions:
- misconception — the student appears to hold an incorrect mental model
  (wrong cause, inverted relationship, false fact framed as belief).
- knowledge_gap — the student has not yet learned the concept (asks for
  explanation, definition, or "what is / how does" without asserting a wrong model).

Rules:
- Prefer knowledge_gap when unsure.
- Use the highlighted passage and lecture excerpt as context when provided.
- Respond with rationale in {target_language}.
- No markdown fences or commentary — JSON only.
"""


def render(inp: QuestionClassifierInput) -> PromptCall:
    """Render a PromptCall for question classification (pure, no I/O)."""
    system = SYSTEM.format(target_language=inp.target_language)
    highlight = inp.highlight_text or "(none)"
    excerpt = inp.lecture_excerpt or "(none)"
    user = (
        f"Question: {inp.question_text}\n"
        f"Highlighted passage: {highlight}\n"
        f"Lecture excerpt:\n{excerpt}\n"
    )
    return PromptCall(
        version=PROMPT_VERSION,
        system=system,
        user=user,
        temperature=0.1,
        max_tokens=256,
    )
