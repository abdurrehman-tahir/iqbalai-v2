"""Teaching Innovation Record API schemas — T-138 (Flow 5 §3.10 #36)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class CoachingSuggestionRead(BaseModel):
    """One pending (unactioned) coaching tip. Coaching framing only — no
    score/grade is ever exposed here (Flow 5 §3.10 locked rule)."""

    id: str
    weakness_type: str
    suggestion: str
    frequency: int
    updated_at: datetime


class CoachingResponseRequest(BaseModel):
    response: Literal["acted", "ignored"]
