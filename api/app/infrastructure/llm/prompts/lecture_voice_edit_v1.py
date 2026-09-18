"""Voice-edit interpretation prompt — T-121 (Flow 5 §3.4 / ARCH §8.6).

Given the current draft + a transcribed teacher instruction, produce ONE
structured edit operation (insert/replace/append/none) plus a short spoken
confirmation — the locked "OT" rule (flow-5 §3.4: "the LLM is given the
current draft + the teacher's transcribed instruction; produces a
structured edit operation"), and the transcription-echo rule (§5.4: "Did
you mean: ...") is satisfied by always including a confirmation the caller
speaks back before/while applying the edit.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.infrastructure.llm.types import PromptCall

PROMPT_VERSION = "lecture_voice_edit.v1"


class DraftParagraphRef(BaseModel):
    ordinal: int
    text: str = Field(max_length=2000)


class VoiceEditInput(BaseModel):
    instruction: str = Field(min_length=1, max_length=2000)
    target_language: Literal["en", "ur", "sd", "ps"] = "en"
    draft_paragraphs: list[DraftParagraphRef] = Field(default_factory=list)


class VoiceEditOutput(BaseModel):
    op: Literal["insert", "replace", "append", "none"]
    ordinal: int | None = None
    text: str | None = Field(default=None, max_length=8000)
    confirmation: str = Field(min_length=1, max_length=1000)


SYSTEM = """You are a voice assistant helping a teacher edit a lecture draft by voice.

Return ONLY valid JSON:
{{
  "op": "insert" | "replace" | "append" | "none",
  "ordinal": <paragraph index to insert-before or replace, omit for append/none>,
  "text": "<new paragraph text, omit for none>",
  "confirmation": "A short spoken confirmation, e.g. 'Adding an example about Newton's third law.'"
}}

CRITICAL RULES:
- "insert": add a new paragraph BEFORE the paragraph at `ordinal`.
- "replace": replace the paragraph at `ordinal` with `text`.
- "append": add a new paragraph at the end of the lecture (omit `ordinal`).
- "none": the teacher asked a question or made a comment with no draft change —
  `confirmation` answers them; `text` and `ordinal` are omitted.
- `confirmation` ALWAYS restates what you understood before acting, e.g.
  "Did you mean: add an example about Newton's third law?" — the teacher hears
  this before the edit is applied.
- Never invent paragraph numbers that don't exist in the draft below.
- Respond in {language}.
- No markdown fences or commentary — JSON only.
"""


def render(input_data: VoiceEditInput) -> PromptCall:
    """Pure render — unit-testable, no I/O."""
    system = SYSTEM.format(language=input_data.target_language)
    lines: list[str] = ["Current draft:"]
    for para in input_data.draft_paragraphs:
        lines.append(f"[{para.ordinal}] {para.text[:500]}")
    lines.append("")
    lines.append(f'Teacher said: "{input_data.instruction}"')
    lines.append("")
    lines.append("Produce the edit operation as JSON.")
    return PromptCall(
        version=PROMPT_VERSION,
        system=system,
        user="\n".join(lines),
        temperature=0.2,
        max_tokens=1000,
    )
