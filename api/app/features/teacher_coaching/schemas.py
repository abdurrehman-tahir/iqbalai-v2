"""Teaching Innovation Record + benchmarking API schemas — T-138/T-139
(Flow 5 §3.10 #36, §3.11 #37)."""

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


class TeacherBenchmarkRead(BaseModel):
    """One positively-framed benchmark row ("Top 23%", never "bottom 30%" —
    Flow 5 §3.11 locked rule). Opted-out / not-yet-computed rows never
    reach this schema (T-139)."""

    id: str
    subject_name: str
    grade_range: str
    region: str
    top_percent: int


class BenchmarkOptOutRequest(BaseModel):
    opted_out: bool
