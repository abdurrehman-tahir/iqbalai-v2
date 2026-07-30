"""Pydantic schemas for school student mode API — T-101."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

StudyModeLiteral = Literal["lecture", "self_study"]


class ModeStateBlob(BaseModel):
    """Per-mode UI restore state (flow-4 §3.4 — no data loss across switches)."""

    model_config = ConfigDict(extra="forbid")

    lecture: dict[str, Any] = Field(default_factory=dict)
    self_study: dict[str, Any] = Field(default_factory=dict)


class StudentModeRead(BaseModel):
    """Current mode + restore blob for the school student dashboard."""

    active_mode: StudyModeLiteral
    mode_state: ModeStateBlob
    lecture_mode_enabled: bool
    self_study_mode_enabled: bool


class StudentModeUpdate(BaseModel):
    """Switch active mode; optionally snapshot the mode being left."""

    active_mode: StudyModeLiteral
    leaving_mode_state: dict[str, Any] | None = None
