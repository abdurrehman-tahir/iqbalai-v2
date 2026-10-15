"""Mini-lecture generation prompt — T-198 (Flow 7 §3.4 / ARCH §8.6).

Shorter sibling of ``lecture_gen_v1``: same JSON shape + source tiers, word
target 800–1200, no web-source instructions (web fallback is disabled by the
caller). Task id ``mini_lecture`` is locked in ARCH §8.4.
"""

from __future__ import annotations

from app.infrastructure.llm.prompts.lecture_gen_v1 import (
    ChunkRef,
    LectureGenerateInput,
    LectureGenerateOutput,
    LectureParagraphOut,
)
from app.infrastructure.llm.types import PromptCall

PROMPT_VERSION = "mini_lecture_gen.v1"
TASK_ID = "mini_lecture"
WORD_TARGET_MIN = 800
WORD_TARGET_MAX = 1200

SYSTEM = """You are a master secondary-school educator writing a SHORT corrective mini-lecture.

Return ONLY valid JSON:
{{
  "title": "Mini-lecture title",
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
- Target length: {word_min}-{word_max} words total across all paragraphs.
- Curriculum sources ([Curriculum]) drive SEQUENCE and STRUCTURE.
- Reference sources ([Ref: …]) drive DEPTH and EXAMPLES.
- Do NOT invent web sources — there is no web tier for mini-lectures.
- Mark each paragraph tier honestly: curriculum, reference, or ai_knowledge.
- Focus on correcting the clustered student misunderstanding described in the topic.
- Respond in {language}.
- No markdown fences or commentary — JSON only.
"""


def render(input_data: LectureGenerateInput) -> PromptCall:
    """Pure render — unit-testable, no I/O."""
    system = SYSTEM.format(
        word_min=WORD_TARGET_MIN,
        word_max=WORD_TARGET_MAX,
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
    if input_data.no_coverage:
        lines.append(
            "NO SOURCES FOUND in curriculum/reference. Do NOT invent facts. "
            "Write one honest ai_knowledge paragraph stating coverage is missing."
        )
        lines.append("")
    lines.append(f"Write the mini-lecture as JSON ({WORD_TARGET_MIN}-{WORD_TARGET_MAX} words).")
    return PromptCall(
        version=PROMPT_VERSION,
        system=system,
        user="\n".join(lines),
        temperature=0.3,
        max_tokens=2500,
    )


__all__ = [
    "PROMPT_VERSION",
    "TASK_ID",
    "WORD_TARGET_MIN",
    "WORD_TARGET_MAX",
    "ChunkRef",
    "LectureGenerateInput",
    "LectureGenerateOutput",
    "LectureParagraphOut",
    "render",
]
