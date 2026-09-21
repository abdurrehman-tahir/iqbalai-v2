"""Quiz generation typed prompt — T-143 (Flow 5 §3.3 / ARCH §8.6 Pattern S)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

PROMPT_VERSION = "quiz_generate.v1"


class QuizGenerateInput(BaseModel):
    topic: str = Field(min_length=1, max_length=500)
    lecture_excerpt: str = Field(min_length=1, max_length=12000)
    target_difficulty: Literal["foundational", "conceptual", "applied", "grade_default"]
    question_count: int = Field(default=7, ge=5, le=10)
    target_language: Literal["en", "ur", "sd", "ps"] = "en"


class QuizQuestionOut(BaseModel):
    stem: str = Field(min_length=1)
    options: list[dict[str, str]] = Field(min_length=2, max_length=6)
    correct_answer: str = Field(min_length=1, max_length=16)
    difficulty: Literal["foundational", "conceptual", "applied", "grade_default"]
    source_excerpt: str = Field(min_length=1, max_length=500)


class QuizGenerateOutput(BaseModel):
    questions: list[QuizQuestionOut] = Field(min_length=5, max_length=10)


SYSTEM = """You are an expert secondary-school assessment writer.

Return ONLY valid JSON:
{{
  "questions": [
    {{
      "stem": "Question text",
      "options": [
        {{"key": "a", "text": "..."}},
        {{"key": "b", "text": "..."}},
        {{"key": "c", "text": "..."}},
        {{"key": "d", "text": "..."}}
      ],
      "correct_answer": "a",
      "difficulty": "foundational" | "conceptual" | "applied" | "grade_default",
      "source_excerpt": "Short quote or paraphrase from the lecture"
    }}
  ]
}}

RULES:
- Write {question_count} multiple-choice questions on the lecture topic.
- Every question MUST include a source_excerpt grounded in the lecture excerpt.
- Match overall difficulty to target_difficulty={target_difficulty}.
- correct_answer must be one of the option keys.
- Language: {target_language}.
"""


def render(inp: QuizGenerateInput) -> list[dict[str, str]]:
    system = SYSTEM.format(
        question_count=inp.question_count,
        target_difficulty=inp.target_difficulty,
        target_language=inp.target_language,
    )
    user = (
        f"Topic: {inp.topic}\n"
        f"Target difficulty: {inp.target_difficulty}\n"
        f"Lecture excerpt:\n{inp.lecture_excerpt}\n"
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
