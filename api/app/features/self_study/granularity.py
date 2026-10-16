"""Study plan granularity bands — T-216 (Flow 8 §3.7)."""

from __future__ import annotations

from datetime import date

from app.features.self_study.models import StudyPlanGranularity


def select_granularity(*, exam_date: date, today: date | None = None) -> StudyPlanGranularity:
    """Auto-select day / 3day / week from exam distance (no user choice at launch)."""
    day = today or date.today()
    days = (exam_date - day).days
    if days <= 14:
        return StudyPlanGranularity.DAY
    if days <= 90:
        return StudyPlanGranularity.THREE_DAY
    return StudyPlanGranularity.WEEK
