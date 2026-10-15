"""Pydantic schemas for self-study entry + state persistence — T-209."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SelfStudyPersistedState(BaseModel):
    """Last-view keys restored when entering self-study (Flow 8 §3.1)."""

    model_config = ConfigDict(extra="forbid")

    last_goal_id: str | None = None
    last_material_id: str | None = None
    last_plan_view: str | None = None


class SelfStudySubscriptionGateRead(BaseModel):
    """No-op gate at launch — limits unset until Flow 13 / M-23."""

    enforced: bool = False
    allowed: bool = True
    max_active_plans: int | None = None
    max_monthly_uploads: int | None = None


class SelfStudyEntryRead(BaseModel):
    """Entering-mode payload for school + independent students."""

    tenant_type: Literal["school", "independent"]
    locked_to_self_study: bool
    active_mode: Literal["lecture", "self_study"]
    state: SelfStudyPersistedState
    subscription_gate: SelfStudySubscriptionGateRead
    # Independent: Lecture-Mode routes must redirect here.
    lecture_mode_redirect_to: str | None = None


class SelfStudyStateUpdate(BaseModel):
    """Partial update of persisted self-study view keys."""

    model_config = ConfigDict(extra="forbid")

    last_goal_id: str | None = Field(default=None)
    last_material_id: str | None = Field(default=None)
    last_plan_view: str | None = Field(default=None)
