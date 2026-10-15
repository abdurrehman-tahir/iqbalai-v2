"""Next-day review cluster criticality scorer — T-197 (Flow 7 §3.1 / ARCH §8.6).

Scores how pedagogically critical a clustered student-misunderstanding is
(0–10). Threshold 7 (locked in Flow 7) gates mini-lecture generation alongside
the frequency rule. Task id ``next_day_review`` is locked in ARCH §8.4.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.infrastructure.llm.types import PromptCall

PROMPT_VERSION = "next_day_review_criticality.v1"
TASK_ID = "next_day_review"


class CriticalityInput(BaseModel):
    """Representative question texts from one cosine cluster."""

    question_texts: list[str] = Field(min_length=1, max_length=40)
    lecture_context: str = Field(default="", max_length=4000)
    target_language: Literal["en", "ur", "sd", "ps"] = "en"


class CriticalityOutput(BaseModel):
    criticality: int = Field(ge=0, le=10)
    rationale: str = Field(default="", max_length=1000)


SYSTEM = """You score how critical a cluster of secondary-school student questions
is for the teacher's next-day review.

Return ONLY valid JSON:
{{
  "criticality": 0-10,
  "rationale": "brief reason"
}}

Scale:
- 0-3 — surface curiosity / wording confusion; low teaching risk
- 4-6 — real gap but recoverable in normal class discussion
- 7-10 — high-stakes misconception or widespread conceptual failure that
  warrants a short corrective mini-lecture tomorrow

Rules:
- Score the CLUSTER as a whole, not any single wording.
- Prefer the lower score when unsure.
- Rationale in {target_language}.
- No markdown fences or commentary — JSON only.
"""


def render(inp: CriticalityInput) -> PromptCall:
    """Render a PromptCall for cluster criticality (pure, no I/O)."""
    system = SYSTEM.format(target_language=inp.target_language)
    numbered = "\n".join(f"{i + 1}. {text}" for i, text in enumerate(inp.question_texts[:40]))
    context = inp.lecture_context or "(none)"
    user = f"Cluster questions:\n{numbered}\n\n" f"Lecture / paragraph context:\n{context}\n"
    return PromptCall(
        version=PROMPT_VERSION,
        system=system,
        user=user,
        temperature=0.1,
        max_tokens=256,
    )
