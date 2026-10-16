"""Study plan refine prompt — T-215 (Flow 8 §3.6 / ARCH §8.6)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.infrastructure.llm.types import PromptCall

PROMPT_VERSION = "study_plan_refine.v1"


class StudyPlanRefineInput(BaseModel):
    refinement_request: str = Field(min_length=1, max_length=2000)
    affected_items_json: str = Field(min_length=1, max_length=20000)


class StudyPlanRefineOutput(BaseModel):
    items: list[dict[str, object]]


SYSTEM = (
    "You refine only the affected study-plan items per the student's natural-language request.\n"
    "Do not invent a whole new plan — rewrite the provided items only.\n"
)


def render(inp: StudyPlanRefineInput) -> PromptCall:
    user = (
        f"Student request: {inp.refinement_request}\n"
        f"Affected items JSON:\n{inp.affected_items_json}\n"
    )
    return PromptCall(
        version=PROMPT_VERSION,
        system=SYSTEM,
        user=user,
        temperature=0.3,
        max_tokens=2000,
    )
