"""Pydantic shapes for Cognitive DNA JSONB columns — T-102 (§4.10)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TopicConfidenceMap(BaseModel):
    """topic_id / topic_name → confidence in [0, 1]."""

    model_config = ConfigDict(extra="forbid")

    scores: dict[str, float] = Field(default_factory=dict)

    @field_validator("scores")
    @classmethod
    def _bounded(cls, value: dict[str, float]) -> dict[str, float]:
        for key, score in value.items():
            if not 0.0 <= score <= 1.0:
                raise ValueError(f"confidence for {key!r} must be between 0 and 1")
        return value

    def to_jsonb(self) -> dict[str, object]:
        return dict(self.scores)

    @classmethod
    def from_jsonb(cls, raw: dict[str, Any] | None) -> TopicConfidenceMap:
        if not raw:
            return cls()
        return cls(scores={str(k): float(v) for k, v in raw.items()})


class FocusArea(BaseModel):
    """A single coaching focus area (never a grade)."""

    model_config = ConfigDict(extra="forbid")

    topic: str = Field(min_length=1, max_length=255)
    reason: str = Field(default="", max_length=2000)


class FocusAreasList(BaseModel):
    """Ordered focus areas for the student."""

    model_config = ConfigDict(extra="forbid")

    areas: list[FocusArea] = Field(default_factory=list)

    def to_jsonb(self) -> list[object]:
        return [area.model_dump() for area in self.areas]

    @classmethod
    def from_jsonb(cls, raw: list[object] | None) -> FocusAreasList:
        if not raw:
            return cls()
        areas: list[FocusArea] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            topic = str(item.get("topic") or "").strip()
            if not topic:
                continue
            # T-106 stores suggestion; schema field is reason — accept both.
            reason = str(item.get("reason") or item.get("suggestion") or "")
            areas.append(FocusArea(topic=topic, reason=reason))
        return cls(areas=areas)
