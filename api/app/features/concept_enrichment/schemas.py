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


# --- T-191 mini-simulation progress -------------------------------------------


class SimulationStateUpdate(BaseModel):
    """Slider values keyed by the sim spec's variable keys."""

    model_config = ConfigDict(extra="forbid")

    values: dict[str, float] = Field(max_length=3)


class SimulationProgressRead(BaseModel):
    """The student's saved sim state for one concept (per-student, T-191).

    ``was_reset`` is true when stored state no longer matched the concept's
    sim spec and was discarded (flow-6 §5.9 "progress was reset" notice).
    """

    model_config = ConfigDict(extra="forbid")

    concept_id: str
    values: dict[str, float] = Field(default_factory=dict)
    updated_at: datetime | None = None
    was_reset: bool = False
