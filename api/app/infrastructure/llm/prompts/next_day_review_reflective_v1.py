"""Next-day review reflective coaching question — T-202 (Flow 7 §3.3 #49 / ARCH §8.6).

One open question about the teacher's OWN teaching practice, grounded in the
day's clusters (e.g. "would a worked example with everyday objects make the
action-reaction pair more concrete?"). CXO rule: coaching, never grading — the
caller rejects evaluative wording with ``contains_grading_language`` and
retries once, omitting the prompt if it still fails (Flow 7 §5.3).
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field

from app.infrastructure.llm.types import PromptCall

PROMPT_VERSION = "next_day_review_reflective.v1"
TASK_ID = "next_day_review"


class ReflectiveInput(BaseModel):
    offering_label: str = Field(max_length=300)
    lecture_topic: str = Field(default="", max_length=500)
    misconceptions: list[str] = Field(min_length=1, max_length=10)
    target_language: Literal["en", "ur", "sd", "ps"] = "en"


class ReflectiveOutput(BaseModel):
    question: str = Field(min_length=1, max_length=600)


SYSTEM = """You are a supportive teaching coach. From the misconceptions students
showed yesterday, write ONE reflective question that invites the teacher to
think about their own teaching approach for tomorrow.

Return ONLY valid JSON:
{{
  "question": "one open question"
}}

Rules:
- Coaching, never grading: do not score, rate, judge, blame or criticise the
  teacher, and never say what they did wrong.
- Ask about a concrete teaching move (an example, analogy, demonstration,
  sequence, check for understanding) tied to the misconceptions.
- One question, under 40 words, ending with a question mark.
- Write in {target_language}.
- No markdown fences or commentary — JSON only.
"""

# English evaluative wording that turns coaching into grading (Flow 7 CXO rule).
_GRADING_RE = re.compile(
    r"\b(score[sd]?|grade[sd]?|grading|rating|rated|poor(ly)?|fail(ed|ing|ure)?|"
    r"wrong|mistake[sn]?|weak(ness)?|bad(ly)?|should have|you didn't|you did not|"
    r"ineffective|unclear explanation)\b",
    re.IGNORECASE,
)


def contains_grading_language(text: str) -> bool:
    """True when the question reads as an evaluation of the teacher."""
    return bool(_GRADING_RE.search(text))


def render(inp: ReflectiveInput) -> PromptCall:
    """Render a PromptCall for the reflective question (pure, no I/O)."""
    system = SYSTEM.format(target_language=inp.target_language)
    items = "\n".join(f"- {m}" for m in inp.misconceptions[:10])
    topic = inp.lecture_topic or "(none)"
    user = (
        f"Class: {inp.offering_label}\nLecture topic: {topic}\n\n"
        f"What students struggled with:\n{items}\n"
    )
    return PromptCall(
        version=PROMPT_VERSION,
        system=system,
        user=user,
        temperature=0.5,
        max_tokens=200,
    )
