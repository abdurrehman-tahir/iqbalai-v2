"""Lecture generation typed prompt — T-116 (Flow 5 §3.2 / ARCH §8.6)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.infrastructure.llm.types import PromptCall

PROMPT_VERSION = "lecture_generate.v1"


class ChunkRef(BaseModel):
    source_id: str
    source_label: str
    tier: Literal["curriculum", "reference", "web"]
    text: str = Field(max_length=4000)


class LectureGenerateInput(BaseModel):
    topic: str = Field(min_length=1, max_length=500)
    teaching_mode: Literal["auto", "manual", "voice_assisted"] = "auto"
    target_language: Literal["en", "ur", "sd", "ps"] = "en"
    curriculum_chunks: list[ChunkRef] = Field(default_factory=list)
    reference_chunks: list[ChunkRef] = Field(default_factory=list)
    # T-119 (#27): populated only when curriculum AND reference retrieval both
    # came back empty — the 3rd escalation tier (SearXNG web search).
    web_chunks: list[ChunkRef] = Field(default_factory=list)
    # T-119: set when curriculum, reference, AND web all came back empty —
    # tells the model to honestly say so instead of inventing content.
    no_coverage: bool = False
    # T-120 (Flow 4 v3 §3.5.4): ADDITIONAL exam-readiness context, never a
    # replacement for curriculum — set only when a PUBLISHED framework is
    # relevant to this lecture's Grade + Subject. Plain fields (not a nested
    # model) so this prompt module has no dependency on the exam_frameworks
    # feature — app/features/lectures/exam_overlay.py fills them in.
    exam_framework_name: str | None = None
    exam_strategy_summary: str | None = None
    exam_priority_topics: list[str] = Field(default_factory=list)


class LectureParagraphOut(BaseModel):
    text: str = Field(min_length=1)
    tier: Literal["curriculum", "reference", "ai_knowledge", "web"] = "ai_knowledge"
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
      "tier": "curriculum" | "reference" | "web" | "ai_knowledge",
      "book_name": null,
      "chunk_id": null
    }}
  ]
}}

CRITICAL RULES:
- Curriculum sources ([Curriculum]) drive SEQUENCE and STRUCTURE — follow their order.
- Reference sources ([Ref: …]) drive DEPTH and EXAMPLES.
- Web sources ([Web: …]) are the LAST-RESORT tier (#27): only present when curriculum AND
  reference had nothing for this topic. Use them like references, tagged "web".
- Prefer curriculum as ground truth; use references and web sources for elaboration.
- Mark each paragraph tier honestly: curriculum, reference, web, or ai_knowledge.
- If exam framework context is present, weave in exam-readiness language (emphasis,
  worked examples) for its high-priority topics — it is ADDITIONAL, never a
  replacement for curriculum sequence/structure.
- Teaching mode = {teaching_mode}: auto=full lecture; manual=outline bullets only;
  voice_assisted=full lecture ready for spoken edits.
- Respond in {language}.
- No markdown fences or commentary — JSON only.
"""

NO_COVERAGE_NOTICE = (
    "NO SOURCES FOUND: curriculum, reference books, and web search all returned nothing "
    "for this topic. Do NOT invent facts. Write a single honest paragraph stating you "
    'don\'t have information on this topic, tagged "ai_knowledge".'
)


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
    for i, chunk in enumerate(input_data.web_chunks, start=1):
        lines.append(f"[Web: {chunk.source_label} {i} | id={chunk.source_id}]")
        lines.append(chunk.text[:2000])
        lines.append("")
    if input_data.no_coverage:
        lines.append(NO_COVERAGE_NOTICE)
        lines.append("")
    if input_data.exam_framework_name:
        lines.append(
            "Exam framework context (ADDITIONAL — supplements curriculum, does NOT "
            f"replace it): {input_data.exam_framework_name}"
        )
        if input_data.exam_strategy_summary:
            lines.append(f"Exam strategy: {input_data.exam_strategy_summary}")
        if input_data.exam_priority_topics:
            lines.append("High-priority exam topics: " + ", ".join(input_data.exam_priority_topics))
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
