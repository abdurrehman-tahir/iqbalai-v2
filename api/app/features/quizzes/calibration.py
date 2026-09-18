"""Per-student quiz calibration from M-08 diagnostic seed (T-144).

BLOCKED-HOOK (Flow 9 / M-18): ``CognitiveDnaCalibrationProvider`` is the
extension point for mastery map / mistake history / pass probability. Until
M-18 ships, ``DiagnosticSeedCalibrationProvider`` is the sole implementation.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from app.features.cognitive_dna.repository import CognitiveDnaRepository
from app.features.quizzes.models import QuizQuestionDifficulty
from app.features.quizzes.schemas import CalibrationProfile, CalibrationSource

# Topic confidence ≥ this → harder / applied questions.
_HIGH_CONFIDENCE = 0.7
# Topic confidence ≤ this (or in focus areas) → foundational.
_LOW_CONFIDENCE = 0.4


class CalibrationContext(Protocol):
    """Inputs passed into quiz generation (stable for M-18 enrichment)."""

    @property
    def profile(self) -> CalibrationProfile: ...

    @property
    def target_difficulty(self) -> QuizQuestionDifficulty: ...


class _ResolvedCalibration:
    __slots__ = ("profile", "target_difficulty")

    def __init__(self, profile: CalibrationProfile, difficulty: QuizQuestionDifficulty) -> None:
        self.profile = profile
        self.target_difficulty = difficulty


class CalibrationProvider(ABC):
    """Strategy interface — swap/enrich with Cognitive DNA in M-18."""

    @abstractmethod
    async def resolve(
        self,
        *,
        student_user_id: str,
        subject_id: str | None,
        lecture_topic: str,
    ) -> _ResolvedCalibration:
        raise NotImplementedError


class DiagnosticSeedCalibrationProvider(CalibrationProvider):
    """M-08 seed only: topic_confidence_jsonb + focus_areas_jsonb."""

    def __init__(self, session: AsyncSession) -> None:
        self._dna = CognitiveDnaRepository(session, "school")

    async def resolve(
        self,
        *,
        student_user_id: str,
        subject_id: str | None,
        lecture_topic: str,
    ) -> _ResolvedCalibration:
        row = await self._dna.get_for_scope(
            student_user_id=student_user_id,
            subject_id=subject_id,
            framework_id=None,
        )
        if row is None:
            profile = CalibrationProfile(
                source=CalibrationSource.GRADE_DEFAULT,
                target_difficulty="grade_default",
                notes="No diagnostic seed; grade-level default difficulty",
            )
            return _ResolvedCalibration(profile, QuizQuestionDifficulty.GRADE_DEFAULT)

        confidence_raw = row.topic_confidence_jsonb or {}
        confidence: dict[str, float] = {}
        for key, value in confidence_raw.items():
            try:
                confidence[str(key)] = float(value)  # type: ignore[arg-type]
            except (TypeError, ValueError):
                continue

        focus_raw = row.focus_areas_jsonb or []
        focus_topics: list[str] = []
        for item in focus_raw:
            if isinstance(item, dict) and "topic" in item:
                focus_topics.append(str(item["topic"]))
            elif isinstance(item, str):
                focus_topics.append(item)

        topic_key = _match_topic(lecture_topic, confidence, focus_topics)
        score = confidence.get(topic_key) if topic_key else None
        in_focus = any(
            _norm(t) in _norm(lecture_topic) or _norm(lecture_topic) in _norm(t)
            for t in focus_topics
        )

        if in_focus or (score is not None and score <= _LOW_CONFIDENCE):
            difficulty = QuizQuestionDifficulty.FOUNDATIONAL
            target: str = "foundational"
        elif score is not None and score >= _HIGH_CONFIDENCE:
            difficulty = QuizQuestionDifficulty.APPLIED
            target = "applied"
        elif score is not None:
            difficulty = QuizQuestionDifficulty.CONCEPTUAL
            target = "conceptual"
        else:
            difficulty = QuizQuestionDifficulty.GRADE_DEFAULT
            target = "grade_default"

        profile = CalibrationProfile(
            source=CalibrationSource.DIAGNOSTIC_SEED,
            topic_confidence=confidence,
            focus_areas=focus_topics,
            target_difficulty=target,  # type: ignore[arg-type]
            notes=f"matched_topic={topic_key or 'none'}; score={score}",
        )
        return _ResolvedCalibration(profile, difficulty)


class CognitiveDnaCalibrationProvider(CalibrationProvider):
    """M-18 hook — NOT implemented. Raises until Flow 9 / M-18 ships."""

    async def resolve(
        self,
        *,
        student_user_id: str,
        subject_id: str | None,
        lecture_topic: str,
    ) -> _ResolvedCalibration:
        raise NotImplementedError(
            "Full Cognitive DNA calibration is Flow 9 / M-18 (BLOCKED). "
            "Use DiagnosticSeedCalibrationProvider until then."
        )


def get_default_calibration_provider(session: AsyncSession) -> CalibrationProvider:
    """Factory — always returns the M-08 diagnostic seed provider for M-11."""
    return DiagnosticSeedCalibrationProvider(session)


def _norm(value: str) -> str:
    return value.strip().lower()


def _match_topic(
    lecture_topic: str, confidence: dict[str, float], focus_topics: list[str]
) -> str | None:
    lt = _norm(lecture_topic)
    for key in confidence:
        if _norm(key) == lt or _norm(key) in lt or lt in _norm(key):
            return key
    for topic in focus_topics:
        if _norm(topic) == lt or _norm(topic) in lt or lt in _norm(topic):
            return topic
    return next(iter(confidence), None)
