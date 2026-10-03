"""API schemas for lecture ratings (T-192)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class LectureRatingSubmit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rating: int = Field(ge=1, le=5)


class MyLectureRatingRead(BaseModel):
    """The caller's OWN rating only — never other students' ratings."""

    model_config = ConfigDict(extra="forbid")

    lecture_id: str
    rating: int | None = None


class LectureRatingSummaryRead(BaseModel):
    """Teacher/staff view: anonymous aggregate only (no ids, no individual values).

    ``average_rating`` is withheld (null) until at least
    ``min_ratings_for_display`` students have rated, so a single student's
    rating can never be read off the "average".
    """

    model_config = ConfigDict(extra="forbid")

    lecture_id: str
    rating_count: int
    min_ratings_for_display: int
    average_rating: float | None = None
    ai_score: int | None = None
    ai_score_max: int
    quality_score: float | None = None
    rating_weight: float
