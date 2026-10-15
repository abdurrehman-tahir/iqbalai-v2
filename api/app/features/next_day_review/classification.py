"""Classify review clusters (frequency + criticality) — T-197 (Flow 7 §3.1).

Frequency qualifies at ≥3 distinct students OR ≥25% of the GSO roster.
Criticality is LLM-scored 0–10 (threshold 7) via the ``next_day_review`` task
prompt. A cluster qualifies for mini-lecture generation (T-198) if either
dimension qualifies. Cluster-level LLM failures write to
``review_classification_failures`` and the rest of the review still ships.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import not_deleted
from app.features.lectures.models import SchoolLecture
from app.features.next_day_review.clustering import QuestionCluster
from app.features.next_day_review.models import ReviewClassificationFailure
from app.features.offerings.models import GradeSubjectOffering
from app.features.student_enrollments.models import StudentEnrollment, StudentEnrollmentStatus
from app.infrastructure.llm.client import chat
from app.infrastructure.llm.prompts.next_day_review_criticality_v1 import (
    TASK_ID,
    CriticalityInput,
    CriticalityOutput,
    render,
)

logger = structlog.get_logger(__name__)

FREQ_MIN_STUDENTS = 3
FREQ_ROSTER_FRACTION = 0.25
CRITICALITY_THRESHOLD = 7


@dataclass
class ClassifiedCluster:
    cluster_ref: str
    bucket_key: str
    items: list[dict[str, Any]]
    unique_student_count: int
    roster_size: int
    freq_score: float
    frequency_qualifies: bool
    criticality: int | None
    criticality_qualifies: bool
    qualifies_for_mini_lecture: bool
    gso_id: str | None = None
    error: str | None = None
    rationale: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "cluster_ref": self.cluster_ref,
            "bucket_key": self.bucket_key,
            "question_ids": [str(i.get("question_id", "")) for i in self.items],
            "unique_student_count": self.unique_student_count,
            "roster_size": self.roster_size,
            "freq_score": self.freq_score,
            "frequency_qualifies": self.frequency_qualifies,
            "criticality": self.criticality,
            "criticality_qualifies": self.criticality_qualifies,
            "qualifies_for_mini_lecture": self.qualifies_for_mini_lecture,
            "gso_id": self.gso_id,
            "error": self.error,
            "rationale": self.rationale,
        }


@dataclass
class ClassificationResult:
    clusters: list[ClassifiedCluster] = field(default_factory=list)
    dlq_written: int = 0

    @property
    def qualifying(self) -> list[ClassifiedCluster]:
        return [c for c in self.clusters if c.qualifies_for_mini_lecture]


def frequency_qualifies(unique_students: int, roster_size: int) -> tuple[bool, float]:
    """Return (qualifies, freq_score).

    ``freq_score`` is the larger of absolute-count ratio to the floor of 3 and
    the roster fraction (clamped), so callers can log a single 0–1-ish signal.
    """
    if unique_students <= 0:
        return False, 0.0
    abs_ok = unique_students >= FREQ_MIN_STUDENTS
    roster_ok = roster_size > 0 and (unique_students / roster_size) >= FREQ_ROSTER_FRACTION
    abs_score = unique_students / FREQ_MIN_STUDENTS
    roster_score = (unique_students / roster_size) if roster_size > 0 else 0.0
    return abs_ok or roster_ok, max(abs_score, roster_score)


def _parse_json_payload(raw: str) -> dict[str, Any]:
    text = raw.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        text = fence.group(1).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        text = text[start : end + 1]
    parsed: object = json.loads(text)
    if not isinstance(parsed, dict):
        raise ValueError("criticality response is not a JSON object")
    return parsed


async def score_criticality(cluster: QuestionCluster) -> CriticalityOutput:
    texts = cluster.question_texts or ["(empty cluster)"]
    prompt = render(
        CriticalityInput(question_texts=texts, lecture_context="", target_language="en")
    )
    raw = await chat(
        [
            {"role": "system", "content": prompt.system},
            {"role": "user", "content": prompt.user},
        ],
        task=TASK_ID,
        temperature=prompt.temperature,
        max_tokens=prompt.max_tokens,
    )
    return CriticalityOutput.model_validate(_parse_json_payload(raw))


async def _roster_size_for_lecture(
    session: AsyncSession, lecture_id: str
) -> tuple[int, str | None]:
    """Return (active enrollment count for the lecture's GSO grade, gso_id)."""
    lec_result = await session.execute(
        select(SchoolLecture).where(
            SchoolLecture.id == lecture_id,
            not_deleted(SchoolLecture),
        )
    )
    lecture = lec_result.scalar_one_or_none()
    if lecture is None or not lecture.grade_subject_offering_id:
        return 0, None
    gso_id = lecture.grade_subject_offering_id
    gso_result = await session.execute(
        select(GradeSubjectOffering).where(
            GradeSubjectOffering.id == gso_id,
            not_deleted(GradeSubjectOffering),
        )
    )
    gso = gso_result.scalar_one_or_none()
    if gso is None:
        return 0, gso_id
    count_result = await session.execute(
        select(func.count())
        .select_from(StudentEnrollment)
        .where(
            StudentEnrollment.grade_id == gso.grade_id,
            StudentEnrollment.academic_session == gso.academic_session,
            StudentEnrollment.status == StudentEnrollmentStatus.ACTIVE,
            not_deleted(StudentEnrollment),
        )
    )
    return int(count_result.scalar_one() or 0), gso_id


async def write_dlq(
    session: AsyncSession,
    *,
    school_id: str,
    gso_id: str,
    cluster_ref: str,
    error: str,
) -> None:
    row = ReviewClassificationFailure(
        school_id=school_id,
        gso_id=gso_id,
        cluster_ref=cluster_ref,
        error=error[:4000],
        failed_at=datetime.now(timezone.utc),
    )
    session.add(row)
    await session.flush()


async def classify_clusters(
    session: AsyncSession,
    *,
    school_id: str,
    clusters: list[QuestionCluster],
) -> ClassificationResult:
    """Classify all clusters; DLQ on criticality failure; never abort the batch."""
    result = ClassificationResult()
    roster_cache: dict[str, tuple[int, str | None]] = {}

    for cluster in clusters:
        lecture_id = ""
        if cluster.items:
            lecture_id = str(cluster.items[0].get("lecture_id") or "")
        if lecture_id not in roster_cache:
            roster_cache[lecture_id] = await _roster_size_for_lecture(session, lecture_id)
        roster_size, gso_id = roster_cache[lecture_id]

        unique = cluster.unique_student_count
        freq_ok, freq_score = frequency_qualifies(unique, roster_size)

        criticality: int | None = None
        crit_ok = False
        rationale = ""
        error: str | None = None
        try:
            scored = await score_criticality(cluster)
            criticality = scored.criticality
            crit_ok = scored.criticality >= CRITICALITY_THRESHOLD
            rationale = scored.rationale
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            logger.warning(
                "review_cluster_criticality_failed",
                cluster_ref=cluster.cluster_ref,
                school_id=school_id,
                error=error,
            )
            if gso_id:
                await write_dlq(
                    session,
                    school_id=school_id,
                    gso_id=gso_id,
                    cluster_ref=cluster.cluster_ref,
                    error=error,
                )
                result.dlq_written += 1
            # Graceful degradation: frequency may still qualify the cluster.

        classified = ClassifiedCluster(
            cluster_ref=cluster.cluster_ref,
            bucket_key=cluster.bucket_key,
            items=list(cluster.items),
            unique_student_count=unique,
            roster_size=roster_size,
            freq_score=freq_score,
            frequency_qualifies=freq_ok,
            criticality=criticality,
            criticality_qualifies=crit_ok,
            qualifies_for_mini_lecture=freq_ok or crit_ok,
            gso_id=gso_id,
            error=error,
            rationale=rationale,
        )
        result.clusters.append(classified)

    await session.commit()
    logger.info(
        "review_classify_complete",
        school_id=school_id,
        cluster_count=len(result.clusters),
        qualifying=len(result.qualifying),
        dlq_written=result.dlq_written,
    )
    return result
