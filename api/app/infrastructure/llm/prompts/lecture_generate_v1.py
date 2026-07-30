"""Lecture generation typed prompt — T-116 (Flow 5 §3.2 / ARCH §8.6)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.infrastructure.llm.types import PromptCall

PROMPT_VERSION = "lecture_generate.v1"


class ChunkRef(BaseModel):
    source_id: str
    source_label: str
    tier: Literal["curriculum", "reference"]
    text: str = Field(max_length=4000)


class LectureGenerateInput(BaseModel):
    topic: str = Field(min_length=1, max_length=500)
    teaching_mode: Literal["auto", "manual", "voice_assisted"] = "auto"
    target_language: Literal["en", "ur", "sd", "ps"] = "en"
    curriculum_chunks: list[ChunkRef] = Field(default_factory=list)
    reference_chunks: list[ChunkRef] = Field(default_factory=list)


class LectureParagraphOut(BaseModel):
    text: str = Field(min_length=1)
    tier: Literal["curriculum", "reference", "ai_knowledge"] = "ai_knowledge"
    book_name: str | None = None
    chunk_id: str | None = None


class LectureGenerateOutput(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    paragraphs: list[LectureParagraphOut] = Field(min_length=1)


SYSTEM = """You are a master secondary-school educator writing a lecture draft.

Return ONLY valid JSON:
{{
  "title": "Lecture title",
  "paragraphs": [
    {{
      "text": "Paragraph body",
      "tier": "curriculum" | "reference" | "ai_knowledge",
      "book_name": null,
      "chunk_id": null
    }}
  ]
}}

CRITICAL RULES:
- Curriculum sources ([Curriculum]) drive SEQUENCE and STRUCTURE — follow their order.
- Reference sources ([Ref: …]) drive DEPTH and EXAMPLES.
- Prefer curriculum as ground truth; use references for elaboration.
- Mark each paragraph tier honestly: curriculum, reference, or ai_knowledge.
- Teaching mode = {teaching_mode}: auto=full lecture; manual=outline bullets only;
  voice_assisted=full lecture ready for spoken edits.
- Respond in {language}.
- No markdown fences or commentary — JSON only.
"""


def render(input_data: LectureGenerateInput) -> PromptCall:
    """Pure render — unit-testable, no I/O."""
    system = SYSTEM.format(
        teaching_mode=input_data.teaching_mode,
        language=input_data.target_language,
    )
    lines: list[str] = [f"Topic: {input_data.topic}", "", "Sources:"]
    for i, chunk in enumerate(input_data.curriculum_chunks, start=1):
        lines.append(f"[Curriculum {i} | {chunk.source_label} | id={chunk.source_id}]")
        lines.append(chunk.text[:2000])
        lines.append("")
    for i, chunk in enumerate(input_data.reference_chunks, start=1):
        lines.append(f"[Ref: {chunk.source_label} {i} | id={chunk.source_id}]")
        lines.append(chunk.text[:2000])
        lines.append("")
    lines.append("Write the lecture as JSON.")
    return PromptCall(
        version=PROMPT_VERSION,
        system=system,
        user="\n".join(lines),
        temperature=0.4,
        max_tokens=4000,
    )


def output_to_dict(output: LectureGenerateOutput) -> dict[str, Any]:
    return output.model_dump(mode="json")
