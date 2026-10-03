"""API schemas for concept enrichment (T-190 / T-191)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class LectureConceptRead(BaseModel):
    """A concept the lecture covers, anchored at its first paragraph."""

    model_config = ConfigDict(extra="forbid")

    concept_id: str
    label: str
    first_paragraph_id: str
    first_paragraph_ordinal: int


class RealWorldUseRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    description: str


class CareerRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    sector: str


class MiniSimVariableRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    label: str
    unit: str = ""
    min: float
    max: float
    step: float
    default: float


class MiniSimOutputRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str
    unit: str = ""
    expression: str


class MiniSimSpecRead(BaseModel):
    """Declarative mini-sim; the client evaluates ``output.expression`` with the
    same safe grammar as ``sim_expression.py`` (never eval)."""

    model_config = ConfigDict(extra="forbid")

    title: str
    scenario: str
    variables: list[MiniSimVariableRead]
    output: MiniSimOutputRead


class ConceptEnrichmentRead(BaseModel):
    """Per-concept enrichment as served to a student.

    ``status=pending`` → generation is queued (cache miss); poll again.
    ``refreshing`` → a stale entry is being regenerated; the content shown is
    still valid ("updated" badge once refreshed, flow-6 §5.9).
    """

    model_config = ConfigDict(extra="forbid")

    concept_id: str
    concept_label: str
    status: Literal["pending", "ready", "failed"]
    real_world_uses: list[RealWorldUseRead] = Field(default_factory=list)
    careers: list[CareerRead] = Field(default_factory=list)
    mini_sim: MiniSimSpecRead | None = None
    generated_at: datetime | None = None
    refreshing: bool = False
