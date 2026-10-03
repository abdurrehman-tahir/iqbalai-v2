"""Concept enrichment: real-world uses + Pakistani careers + mini-sim — T-190.

Flow 6 §3.10 (#71) / ARCH §8.6. One call per CONCEPT (cached and shared by
every student), so the output is generic, curriculum-level content — never
student-specific. Careers are chosen ONLY from the supplied vocabulary ids;
the caller drops any id that is not in the ``careers`` table.

The mini-simulation is a declarative spec (sliders + one arithmetic output
expression) that the client evaluates with a tiny safe parser — no code is
ever executed from model output.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.infrastructure.llm.types import PromptCall

PROMPT_VERSION = "concept_enrichment.v1"


class CareerOption(BaseModel):
    id: str = Field(min_length=1, max_length=36)
    name: str = Field(min_length=1, max_length=200)
    sector: str = Field(min_length=1, max_length=100)


class ConceptEnrichmentInput(BaseModel):
    concept_label: str = Field(min_length=1, max_length=500)
    careers: list[CareerOption] = Field(min_length=1, max_length=200)
    target_language: Literal["en", "ur", "sd", "ps"] = "en"


class RealWorldUseOut(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=1000)


class SimVariableOut(BaseModel):
    key: str = Field(pattern=r"^[a-z][a-z0-9_]{0,23}$")
    label: str = Field(min_length=1, max_length=80)
    unit: str = Field(default="", max_length=20)
    min: float
    max: float
    step: float = Field(gt=0)
    default: float


class SimOutputOut(BaseModel):
    label: str = Field(min_length=1, max_length=80)
    unit: str = Field(default="", max_length=20)
    # Arithmetic over variable keys only: + - * / ^ ( ) and numbers.
    expression: str = Field(min_length=1, max_length=200)


class MiniSimOut(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    scenario: str = Field(min_length=1, max_length=600)
    variables: list[SimVariableOut] = Field(min_length=1, max_length=3)
    output: SimOutputOut


class ConceptEnrichmentOutput(BaseModel):
    real_world_uses: list[RealWorldUseOut] = Field(min_length=2, max_length=4)
    career_ids: list[str] = Field(default_factory=list, max_length=4)
    mini_sim: MiniSimOut | None = None


SYSTEM = """You help secondary-school students in Pakistan see why a concept matters.

Return ONLY valid JSON:
{{
  "real_world_uses": [{{"title": "...", "description": "..."}}],
  "career_ids": ["<id from the CAREERS list>"],
  "mini_sim": {{
    "title": "...",
    "scenario": "...",
    "variables": [
      {{"key": "mass", "label": "Mass", "unit": "kg",
        "min": 1, "max": 100, "step": 1, "default": 10}}
    ],
    "output": {{"label": "Force", "unit": "N", "expression": "mass * acceleration"}}
  }}
}}

CRITICAL RULES:
- real_world_uses: 2-4 concrete uses of the concept, recognisable in Pakistan
  (e.g. local industry, agriculture, infrastructure, everyday life).
- career_ids: up to 4 ids copied EXACTLY from the CAREERS list below. Never invent
  careers or ids. Use [] if none genuinely fit.
- mini_sim: a tiny "what if" explorer. 1-3 numeric variables (key: lowercase letters,
  digits, underscore) with sensible min/max/step/default, and ONE output whose
  "expression" uses ONLY those variable keys, numbers, + - * / ^ and parentheses.
  If the concept cannot be expressed as a formula, set "mini_sim": null.
- Respond in {language}. Keep keys and expressions in English.
- No markdown fences or commentary — JSON only.
"""


def render(input_data: ConceptEnrichmentInput) -> PromptCall:
    """Pure render — unit-testable, no I/O."""
    careers = "\n".join(f"- {c.id} | {c.name} ({c.sector})" for c in input_data.careers)
    user = (
        f"Concept: {input_data.concept_label}\n\n"
        f"CAREERS (id | name):\n{careers}\n\n"
        "Generate the real-world uses, matching career ids, and mini-simulation as JSON."
    )
    return PromptCall(
        version=PROMPT_VERSION,
        system=SYSTEM.format(language=input_data.target_language),
        user=user,
        temperature=0.4,
        max_tokens=1200,
    )
