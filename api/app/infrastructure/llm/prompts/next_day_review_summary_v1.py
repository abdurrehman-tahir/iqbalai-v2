"""Next-day review card AI summary — T-200 (Flow 7 §3.1 / ARCH §8.6).

Produces the 2–3 sentence summary at the top of a teacher's review card from
the day's classified clusters for one Grade-Subject offering. Written in the
teacher's UI language (Flow 7 §11); student wording stays in its original
language. Task id ``next_day_review`` is locked in ARCH §8.4.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.infrastructure.llm.types import PromptCall

PROMPT_VERSION = "next_day_review_summary.v1"
TASK_ID = "next_day_review"


class ReviewClusterBrief(BaseModel):
    """One cluster as the summarizer sees it — counts + representative wording."""

    representative_question: str = Field(max_length=1000)
    question_count: int = Field(ge=1)
    unique_student_count: int = Field(ge=1)
    critical: bool = False


class ReviewSummaryInput(BaseModel):
    offering_label: str = Field(max_length=300)
    lecture_topic: str = Field(default="", max_length=500)
    clusters: list[ReviewClusterBrief] = Field(min_length=1, max_length=20)
    target_language: Literal["en", "ur", "sd", "ps"] = "en"


class ReviewSummaryOutput(BaseModel):
    summary: str = Field(min_length=1, max_length=1200)


SYSTEM = """You write the opening summary of a teacher's daily review card.
Yesterday's student questions for one class were clustered by topic; you see
each cluster's representative question and how many students asked.

Return ONLY valid JSON:
{{
  "summary": "2-3 sentences"
}}

Rules:
- 2-3 sentences, plain and specific: what students struggled with most and
  which misconception looks most critical.
- Describe the class's understanding — never grade or judge the teacher.
- Never name or single out individual students.
- Write the summary in {target_language}; quote student wording unchanged.
- No markdown fences or commentary — JSON only.
"""


def render(inp: ReviewSummaryInput) -> PromptCall:
    """Render a PromptCall for the review-card summary (pure, no I/O)."""
    system = SYSTEM.format(target_language=inp.target_language)
    lines = "\n".join(
        f"{i + 1}. [{'critical' if c.critical else 'frequent'}] "
        f"{c.question_count} questions from {c.unique_student_count} students: "
        f"{c.representative_question}"
        for i, c in enumerate(inp.clusters[:20])
    )
    topic = inp.lecture_topic or "(none)"
    user = f"Class: {inp.offering_label}\nLecture topic: {topic}\n\nClusters:\n{lines}\n"
    return PromptCall(
        version=PROMPT_VERSION,
        system=system,
        user=user,
        temperature=0.3,
        max_tokens=400,
    )
