"""Study plan create prompt — T-215 (Flow 8 §3.6 / ARCH §8.6)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.infrastructure.llm.types import PromptCall

PROMPT_VERSION = "study_plan_create.v1"


class WeightedTopic(BaseModel):
    topic_label: str
    weight: float


class StudyPlanCreateInput(BaseModel):
    exam_name: str = Field(min_length=1, max_length=200)
    exam_date: str = Field(min_length=1, max_length=32)
    daily_hours: int = Field(ge=1, le=12)
    strong_topics: list[str] = Field(default_factory=list)
    weighted_topics: list[WeightedTopic] = Field(min_length=1)
    granularity: str = Field(min_length=1, max_length=16)


class StudyPlanCreateOutput(BaseModel):
    items: list[dict[str, object]]


SYSTEM = (
    "You build a secondary-school study plan from weighted exam topics.\n"
    "Prioritise higher-weight topics earlier. Lighten coverage of strong topics.\n"
    "Return concrete study blocks matching the requested granularity.\n"
)


def render(inp: StudyPlanCreateInput) -> PromptCall:
    topics = "\n".join(f"- {t.topic_label} (weight={t.weight:.3f})" for t in inp.weighted_topics)
    strong = ", ".join(inp.strong_topics) if inp.strong_topics else "(none)"
    user = (
        f"Exam: {inp.exam_name}\n"
        f"Exam date: {inp.exam_date}\n"
        f"Daily hours: {inp.daily_hours}\n"
        f"Strong topics: {strong}\n"
        f"Granularity: {inp.granularity}\n"
        f"Weighted topics:\n{topics}\n"
    )
    return PromptCall(
        version=PROMPT_VERSION,
        system=SYSTEM,
        user=user,
        temperature=0.3,
        max_tokens=3000,
    )
