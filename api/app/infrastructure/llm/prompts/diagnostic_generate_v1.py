"""Diagnostic question generation prompt — T-104 (Flow 4 §3.6 / ARCH §8.6)."""

from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.infrastructure.llm.types import PromptCall

PROMPT_VERSION = "diagnostic_generate.v1"
_MIN_QUESTIONS = 15
_MAX_QUESTIONS = 25
_MAX_CONTEXT_CHARS = 10_000


class DiagnosticGenerateInput(BaseModel):
    """Calibration context for school (grade+subject tree) or independent (framework)."""

    target_language: Literal["en", "ur", "sd", "ps"] = "en"
    tenant_kind: Literal["school", "independent"]
    grade_label: str = ""
    subject_name: str = ""
    framework_name: str = ""
    # Compact JSON-serializable context (topic tree or prioritized topics).
    context_json: dict[str, Any] = Field(default_factory=dict)
    question_count: int = Field(default=20, ge=_MIN_QUESTIONS, le=_MAX_QUESTIONS)


class GeneratedDiagnosticQuestion(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    prompt: str = Field(min_length=1, max_length=4000)
    choices: list[str] = Field(default_factory=list)
    topic: str = Field(default="", max_length=255)


class DiagnosticGenerateOutput(BaseModel):
    questions: list[GeneratedDiagnosticQuestion] = Field(min_length=_MIN_QUESTIONS)


SYSTEM = """You generate diagnostic assessment questions for secondary-school students.

Return ONLY valid JSON matching this schema:
{{
  "questions": [
    {{
      "id": "q1",
      "prompt": "Question text",
      "choices": ["A", "B", "C", "D"],
      "topic": "Topic name"
    }}
  ]
}}

Rules:
- Produce exactly {question_count} questions (between 15 and 25 inclusive).
- Calibrate difficulty to the provided grade / subject / exam-framework context.
- Prefer topics with higher priority_weight when present.
- Multiple-choice with 3–4 choices when possible; open-ended (empty choices) is allowed sparingly.
- Questions diagnose gaps — they are NOT graded exams. Avoid punitive wording.
- Respond in {language} for all question text and choices.
- No markdown fences or commentary — JSON only.
"""


def _truncate_context(context: dict[str, Any], limit: int = _MAX_CONTEXT_CHARS) -> str:
    raw = json.dumps(context, ensure_ascii=False, indent=2)
    if len(raw) <= limit:
        return raw
    return raw[:limit] + "\n… [context truncated]"


def render(input_data: DiagnosticGenerateInput) -> PromptCall:
    """Render a PromptCall for diagnostic question generation (pure, no I/O)."""
    system = SYSTEM.format(
        question_count=input_data.question_count,
        language=input_data.target_language,
    )
    if input_data.tenant_kind == "school":
        header = (
            f"Tenant: school\n"
            f"Grade: {input_data.grade_label.strip() or 'unknown'}\n"
            f"Subject: {input_data.subject_name.strip() or 'unknown'}\n"
        )
    else:
        header = (
            f"Tenant: independent\n"
            f"Exam framework: {input_data.framework_name.strip() or 'unknown'}\n"
        )
    user = (
        f"{header}\n"
        f"Calibration context (JSON):\n{_truncate_context(input_data.context_json)}\n\n"
        f"Generate exactly {input_data.question_count} diagnostic questions as JSON."
    )
    return PromptCall(
        version=PROMPT_VERSION,
        system=system,
        user=user,
        temperature=0.4,
        max_tokens=8192,
    )
