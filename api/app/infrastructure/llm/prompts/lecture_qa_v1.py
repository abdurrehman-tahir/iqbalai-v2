"""Lecture Q&A typed prompt — T-158 (Flow 6 §3.4 / ARCH §8.6).

Grounded student answers over Pattern S dual-RAG curriculum + reference chunks,
with optional web fallback (#27) and exam-framework overlay (T-161 / §8.21).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.infrastructure.llm.types import PromptCall

PROMPT_VERSION = "lecture_qa.v1"


class QaChunkRef(BaseModel):
    source_id: str
    source_label: str
    tier: Literal["curriculum", "reference", "web", "ai_knowledge"]
    text: str = Field(max_length=4000)


class LectureQaInput(BaseModel):
    question_text: str = Field(min_length=1, max_length=4000)
    highlight_text: str | None = Field(default=None, max_length=4000)
    lecture_topic: str = Field(default="", max_length=500)
    target_language: Literal["en", "ur", "sd", "ps"] = "en"
    curriculum_chunks: list[QaChunkRef] = Field(default_factory=list)
    reference_chunks: list[QaChunkRef] = Field(default_factory=list)
    web_chunks: list[QaChunkRef] = Field(default_factory=list)
    # True when curriculum + reference were empty and web also failed / stubbed.
    no_coverage: bool = False
    web_stub_notice: str | None = None
    # T-161: ADDITIONAL exam-readiness context when this student has a framework.
    exam_framework_name: str | None = None
    exam_strategy_summary: str | None = None
    exam_priority_topics: list[str] = Field(default_factory=list)
    # Prior turns in the same conversation (follow-ups), oldest first.
    conversation_history: list[str] = Field(default_factory=list)


class LectureQaSourceSpan(BaseModel):
    """Provenance span for the answer panel deep-link (T-158 / T-159)."""

    badge: str
    tier: Literal["curriculum", "reference", "ai_knowledge", "web", "no_source"]
    chunk_id: str | None = None
    book_name: str | None = None
    excerpt: str = ""
    source_url: str | None = None


class LectureQaOutput(BaseModel):
    """Structured metadata companion to the streamed free-text answer.

    The streamed body is the student-facing answer; this model documents the
    badge / span contract stored in ``answer_source_tags_jsonb``.
    """

    answer_text: str = Field(min_length=1)
    primary_badge: str
    source_spans: list[LectureQaSourceSpan] = Field(default_factory=list)


SYSTEM = (
    "You are a secondary-school tutor answering a student's question "
    "while they study a lecture.\n"
    "\n"
    "Rules:\n"
    "- Answer ONLY from the provided sources when present. Prefer curriculum, "
    "then reference, then web.\n"
    "- If web stub / no_coverage notices are present, say clearly that you lack "
    "grounded sources — do not invent facts.\n"
    "- Cite provenance inline using badges: [Curriculum], [Ref: Book Name], "
    "[AI Knowledge], [Web], or [No Source].\n"
    "- If exam framework context is present, weave exam-relevant emphasis and "
    "terminology into the answer —\n"
    "  ADDITIONAL polish only; never contradict curriculum sources; never "
    "rewrite the lecture body.\n"
    "- Answer in {target_language}. Keep the tone of any persona block "
    "prepended above this message.\n"
    "- Be concise and clear for a secondary-school student. No markdown fences.\n"
)


def render(inp: LectureQaInput) -> PromptCall:
    """Render a PromptCall for lecture Q&A (pure, no I/O)."""
    system = SYSTEM.format(target_language=inp.target_language)
    lines: list[str] = []
    if inp.lecture_topic:
        lines.append(f"Lecture topic: {inp.lecture_topic}")
    if inp.highlight_text:
        lines.append(f"Highlighted passage: {inp.highlight_text}")
    lines.append(f"Question: {inp.question_text}")
    lines.append("")
    lines.append("Sources:")
    for i, chunk in enumerate(inp.curriculum_chunks, start=1):
        lines.append(f"[Curriculum {i} | {chunk.source_label} | id={chunk.source_id}]")
        lines.append(chunk.text[:2000])
        lines.append("")
    for i, chunk in enumerate(inp.reference_chunks, start=1):
        lines.append(f"[Ref: {chunk.source_label} {i} | id={chunk.source_id}]")
        lines.append(chunk.text[:2000])
        lines.append("")
    for i, chunk in enumerate(inp.web_chunks, start=1):
        lines.append(f"[Web: {chunk.source_label} {i} | id={chunk.source_id}]")
        lines.append(chunk.text[:2000])
        lines.append("")
    if inp.web_stub_notice:
        lines.append(inp.web_stub_notice)
        lines.append("")
    if inp.no_coverage:
        lines.append(
            "NO SOURCES FOUND: curriculum, reference, and web all returned nothing. "
            "Do NOT invent facts. State clearly that you don't have information, "
            "and badge the answer [No Source]."
        )
        lines.append("")
    if inp.exam_framework_name:
        lines.append(
            "Exam framework context (ADDITIONAL — supplements curriculum, does NOT "
            f"replace it): {inp.exam_framework_name}"
        )
        if inp.exam_strategy_summary:
            lines.append(f"Exam strategy: {inp.exam_strategy_summary}")
        if inp.exam_priority_topics:
            lines.append(
                "High-priority exam topics: " + ", ".join(inp.exam_priority_topics)
            )
        lines.append("")
    if inp.conversation_history:
        lines.append("Earlier turns in this conversation:")
        for turn in inp.conversation_history:
            lines.append(f"- {turn}")
        lines.append("")
    lines.append("Write the answer now.")
    return PromptCall(
        version=PROMPT_VERSION,
        system=system,
        user="\n".join(lines),
        temperature=0.3,
        max_tokens=1024,
    )
