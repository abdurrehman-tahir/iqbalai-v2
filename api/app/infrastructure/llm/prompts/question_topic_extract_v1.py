"""Question → topic extraction prompt — T-214 (Flow 8 §3.5 / ARCH §8.6)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.infrastructure.llm.types import PromptCall

PROMPT_VERSION = "question_topic_extract.v1"


class QuestionTopicExtractInput(BaseModel):
    questions: list[str] = Field(min_length=1, max_length=500)
    syllabus_topics: list[str] = Field(default_factory=list)


class QuestionTopicExtractOutput(BaseModel):
    topics: list[str] = Field(min_length=1)


SYSTEM = (
    "You classify exam-prep questions into curriculum topics.\n"
    "Return one short topic label per question, in the same order.\n"
    "Prefer syllabus topic names when provided; otherwise use free-text labels.\n"
)


def render(inp: QuestionTopicExtractInput) -> PromptCall:
    syllabus = (
        "Syllabus topics:\n" + "\n".join(f"- {t}" for t in inp.syllabus_topics) + "\n"
        if inp.syllabus_topics
        else "No syllabus list provided — invent concise free-text topics.\n"
    )
    numbered = "\n".join(f"{i}. {q}" for i, q in enumerate(inp.questions, start=1))
    user = f"{syllabus}\nQuestions:\n{numbered}\n"
    return PromptCall(
        version=PROMPT_VERSION,
        system=SYSTEM,
        user=user,
        temperature=0.2,
        max_tokens=2000,
    )
