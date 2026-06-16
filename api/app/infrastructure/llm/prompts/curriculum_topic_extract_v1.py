"""Curriculum topic-tree extraction prompt — T-057 (Flow 3 §3.3 #18)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.infrastructure.llm.types import PromptCall

PROMPT_VERSION = "curriculum_topic_extract.v1"
_MAX_DOCUMENT_CHARS = 12_000


class CurriculumTopicExtractInput(BaseModel):
    title: str
    language: Literal["en", "ur", "sd", "ps"] = "en"
    document_text: str = Field(min_length=1)


class TopicSection(BaseModel):
    title: str
    sub_topics: list[str] = Field(default_factory=list)


class TopicChapter(BaseModel):
    title: str
    sections: list[TopicSection] = Field(default_factory=list)


class CurriculumTopicExtractOutput(BaseModel):
    chapters: list[TopicChapter] = Field(default_factory=list)


SYSTEM = """You extract a curriculum topic hierarchy from textbook or syllabus text.

Return ONLY valid JSON matching this schema:
{
  "chapters": [
    {
      "title": "Chapter title",
      "sections": [
        {
          "title": "Section title",
          "sub_topics": ["Sub-topic A", "Sub-topic B"]
        }
      ]
    }
  ]
}

Rules:
- Build chapter → section → sub-topic hierarchy from headings and outline structure.
- Preserve original topic titles; do not invent content not suggested by the text.
- Use concise titles; sub_topics are leaf topics under each section.
- If the document lacks clear structure, infer reasonable chapters/sections from content groupings.
- Respond in {language} for all titles.
- No markdown fences or commentary — JSON only.
"""


def _truncate(text: str, limit: int = _MAX_DOCUMENT_CHARS) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "\n\n[… document truncated for extraction …]"


def render(input_data: CurriculumTopicExtractInput) -> PromptCall:
    """Render a PromptCall for curriculum topic extraction."""
    system = SYSTEM.replace("{language}", input_data.language)
    body = _truncate(input_data.document_text.strip())
    user = (
        f"Curriculum title: {input_data.title.strip()}\n\n"
        f"Document text:\n{body}\n\n"
        "Extract the topic tree JSON."
    )
    return PromptCall(
        version=PROMPT_VERSION,
        system=system,
        user=user,
        temperature=0.2,
        max_tokens=4096,
    )
