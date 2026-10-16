"""Self-study session typed prompt — T-211 (Flow 8 §3.2 / ARCH §8.6).

Injects the student's daily goal so the tutor steers explanations toward it.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.infrastructure.llm.types import PromptCall

PROMPT_VERSION = "self_study_session.v1"


class SelfStudySessionInput(BaseModel):
    question_text: str = Field(min_length=1, max_length=4000)
    daily_goal: str | None = Field(default=None, max_length=2000)
    target_language: Literal["en", "ur", "sd", "ps"] = "en"
    material_title: str | None = Field(default=None, max_length=500)


class SelfStudySessionOutput(BaseModel):
    answer_text: str = Field(min_length=1)
    referenced_goal: bool = False


SYSTEM = (
    "You are a secondary-school tutor in a student's self-study session.\n"
    "\n"
    "Rules:\n"
    "- Respond in {target_language}.\n"
    "- If a daily goal is provided, steer explanations toward that goal and "
    "reference it when helpful — never invent a different goal.\n"
    "- Prefer clear, step-by-step teaching over encyclopedic dumps.\n"
    "- If the question is unrelated to the goal, still answer, then gently "
    "connect back to the goal when natural.\n"
)


def render(inp: SelfStudySessionInput) -> PromptCall:
    """Pure render — no I/O (ARCH §8.6)."""
    system = SYSTEM.format(target_language=inp.target_language)
    goal_block = (
        f"Student's daily goal: {inp.daily_goal}\n"
        if inp.daily_goal
        else "Student's daily goal: (not set)\n"
    )
    material = f"Current material: {inp.material_title}\n" if inp.material_title else ""
    user = f"{goal_block}{material}" f"Student question:\n{inp.question_text}\n"
    return PromptCall(
        version=PROMPT_VERSION,
        system=system,
        user=user,
        temperature=0.4,
        max_tokens=2000,
    )
