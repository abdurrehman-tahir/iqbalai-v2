"""Teaching Innovation Record suggestion generator — T-138 (Flow 5 §3.10 #36, ARCH §8.6).

A separate, small LLM call (task="scoring" — same tier as the 7-dim
evaluator, no dedicated coaching model exists) that turns a detected
recurring weakness into ONE short, supportive coaching tip. Locked framing
(Flow 5 §3.10): **coaching, never grading** — the model is explicitly told
it is a mentor, not an evaluator, and must never state or imply a score.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.infrastructure.llm.types import PromptCall

PROMPT_VERSION = "teacher_coaching.v1"


class TeacherCoachingInput(BaseModel):
    weakness_type: str = Field(min_length=1, max_length=100)
    frequency: int = Field(ge=1)
    last_suggestion: str | None = None
    teacher_response: Literal["acted", "ignored", "none"] = "none"
    region: str | None = None


class TeacherCoachingOutput(BaseModel):
    suggestion: str = Field(min_length=1, max_length=300)


SYSTEM = """You are a warm, encouraging teaching mentor helping a secondary-school \
teacher grow their lecture-writing craft. You are NOT grading or scoring — never \
mention scores, numbers, or "you failed at X." Frame everything as a friendly, \
actionable tip a supportive colleague would share.

You will be told which quality a teacher's lectures have recently been weaker on \
(e.g. "originality", "cultural_relevance"), how many times this has recurred, and \
how the teacher responded to your last tip on this topic.

CRITICAL RULE — if the teacher's last response was "ignored" and this is a repeat \
occurrence, your previous angle did not land. Do NOT repeat or lightly reword the \
previous suggestion — propose a genuinely different approach instead (a different \
technique, framing, or entry point). If there is no prior suggestion, or the \
teacher acted on it, a fresh, natural tip for this weakness is fine.

Return ONLY valid JSON, no markdown fences, no commentary:
{{"suggestion": "<one short, warm, actionable sentence>"}}"""


def render(input_data: TeacherCoachingInput) -> PromptCall:
    """Pure render — unit-testable, no I/O."""
    lines = [
        f"Recurring weakness: {input_data.weakness_type}",
        f"Times observed: {input_data.frequency}",
        f"Teacher's region: {input_data.region or 'unknown'}",
    ]
    if input_data.last_suggestion:
        lines.append(f"Your previous suggestion for this weakness: {input_data.last_suggestion}")
        lines.append(f"Teacher's response to it: {input_data.teacher_response}")
    else:
        lines.append("No previous suggestion for this weakness yet.")
    lines.append("")
    lines.append("Write the coaching tip as JSON.")

    return PromptCall(
        version=PROMPT_VERSION,
        system=SYSTEM,
        user="\n".join(lines),
        temperature=0.6,
        max_tokens=200,
    )
