"""Review card assembly + 05:00 SLA + 06:00 notify — T-200 (Flow 7 §3.1).

After a school's clusters are classified and its mini-lectures generated, one
``lecture_reviews`` row is assembled per Grade-Subject offering: AI summary,
the High-Frequency / Critical cluster snapshot and the mini-lecture reference.
Clusters that hit the DLQ still ship on frequency alone (graceful degradation).

Timing (Asia/Karachi): questions asked on day D are aggregated at 23:00 D,
must all be assembled by 05:00 D+1 (else Platform-Admin alert) and the teacher
is notified at 06:00 D+1 — never earlier, enforced both by the beat time and by
``notify_ready_reviews`` itself.
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import date, datetime, time, timedelta, timezone
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.audit.actions import REVIEW_SLA_BREACHED
from app.features.grades.models import Grade
from app.features.lectures.lecture_notifications import _resolve_recipient
from app.features.lectures.models import SchoolLecture
from app.features.next_day_review.aggregation import (
    KARACHI,
    QUESTION_EVENT_TYPES,
    karachi_day_bounds,
)
from app.features.next_day_review.classification import ClassifiedCluster
from app.features.next_day_review.models import LectureReview, LectureReviewStatus
from app.features.next_day_review.reflection import generate_reflective_prompt
from app.features.next_day_review.schemas import ReviewClusterQuestion, ReviewClusterSnapshot
from app.features.offerings.models import GradeSubjectOffering
from app.features.student_events.models import SchoolStudentEvent, StudentEventTenantType
from app.features.subjects.models import Subject
from app.features.teacher_onboarding.models import TeacherProfile
from app.infrastructure.audit.log import audit
from app.infrastructure.llm.client import chat
from app.infrastructure.llm.prompts.next_day_review_summary_v1 import (
    TASK_ID,
    ReviewClusterBrief,
    ReviewSummaryInput,
    ReviewSummaryOutput,
)
from app.infrastructure.llm.prompts.next_day_review_summary_v1 import render as render_summary
from app.infrastructure.notifications.lectures import notify_lecture_event
from app.infrastructure.notifications.system import notify_all_platform_admins

logger = structlog.get_logger(__name__)

NOTIFY_LOCAL_TIME = time(6, 0)
SLA_LOCAL_TIME = time(5, 0)
REVIEW_READY_TEMPLATE = "lectures.next_day_review_ready"
SLA_BREACH_TEMPLATE = "system.review_sla_breach"
SUPPORTED_LANGUAGES = frozenset({"en", "ur", "sd", "ps"})


def _local_at(review_date: date, at: time) -> datetime:
    """``at`` on the morning after ``review_date`` (Karachi), as an aware datetime."""
    return datetime.combine(review_date + timedelta(days=1), at, tzinfo=KARACHI)


def notify_not_before(review_date: date) -> datetime:
    return _local_at(review_date, NOTIFY_LOCAL_TIME)


def sla_deadline(review_date: date) -> datetime:
    return _local_at(review_date, SLA_LOCAL_TIME)


def previous_review_date(now: datetime | None = None) -> date:
    """The question day a 05:00/06:00 run is about — yesterday in Karachi."""
    current = (now or datetime.now(timezone.utc)).astimezone(KARACHI)
    return current.date() - timedelta(days=1)


def build_snapshot(
    cluster: ClassifiedCluster, mini_lecture_id: str | None
) -> ReviewClusterSnapshot | None:
    """Snapshot one qualifying cluster for the card; ``None`` if it doesn't qualify."""
    if not cluster.qualifies_for_mini_lecture or not cluster.items:
        return None
    questions = [
        ReviewClusterQuestion(
            question_id=str(item.get("question_id") or ""),
            student_user_id=str(item.get("user_id") or ""),
            question_text=str(item.get("question_text") or ""),
            paragraph_id=item.get("paragraph_id"),
            source_chunk_id=item.get("source_chunk_id"),
            occurred_at=item.get("occurred_at"),
        )
        for item in cluster.items
    ]
    representative = next((q.question_text for q in questions if q.question_text), "")
    return ReviewClusterSnapshot(
        cluster_ref=cluster.cluster_ref,
        lecture_id=str(cluster.items[0].get("lecture_id") or ""),
        column="critical" if cluster.criticality_qualifies else "high_frequency",
        question_count=len(questions),
        unique_student_count=cluster.unique_student_count,
        criticality=cluster.criticality,
        freq_score=round(cluster.freq_score, 3),
        representative_question=representative[:1000],
        mini_lecture_id=mini_lecture_id,
        questions=questions,
    )


def _parse_json(raw: str) -> dict[str, Any]:
    text = raw.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        text = fence.group(1).strip()
    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        text = text[start : end + 1]
    parsed: object = json.loads(text)
    if not isinstance(parsed, dict):
        raise ValueError("summary response is not a JSON object")
    return parsed


async def generate_summary(
    snapshots: list[ReviewClusterSnapshot],
    *,
    offering_label: str,
    lecture_topic: str,
    target_language: str,
) -> str:
    """2–3 sentence card summary; empty string on LLM failure (card still ships)."""
    briefs = [
        ReviewClusterBrief(
            representative_question=s.representative_question or s.cluster_ref,
            question_count=max(s.question_count, 1),
            unique_student_count=max(s.unique_student_count, 1),
            critical=s.column == "critical",
        )
        for s in snapshots[:20]
    ]
    lang = target_language if target_language in SUPPORTED_LANGUAGES else "en"
    prompt = render_summary(
        ReviewSummaryInput(
            offering_label=offering_label[:300],
            lecture_topic=lecture_topic[:500],
            clusters=briefs,
            target_language=lang,  # type: ignore[arg-type]
        )
    )
    try:
        raw = await chat(
            [
                {"role": "system", "content": prompt.system},
                {"role": "user", "content": prompt.user},
            ],
            task=TASK_ID,
            temperature=prompt.temperature,
            max_tokens=prompt.max_tokens,
        )
        return ReviewSummaryOutput.model_validate(_parse_json(raw)).summary
    except Exception as exc:
        # Deliberate: a summary failure must not block the card (Flow 7 §3.1
        # partial-review rule) — the clusters + mini-lecture still ship.
        logger.warning("review_summary_failed", error=f"{type(exc).__name__}: {exc}")
        return ""


async def _offering_label(session: AsyncSession, gso_id: str) -> str:
    result = await session.execute(
        select(Grade.name, Subject.name)
        .select_from(GradeSubjectOffering)
        .join(Grade, Grade.id == GradeSubjectOffering.grade_id)
        .join(Subject, Subject.id == GradeSubjectOffering.subject_id)
        .where(GradeSubjectOffering.id == gso_id)
    )
    row = result.first()
    return f"{row[0]} {row[1]}" if row else ""


async def _teacher_language(session: AsyncSession, teacher_user_id: str | None) -> str:
    if not teacher_user_id:
        return "en"
    profile = await session.get(TeacherProfile, teacher_user_id)
    lang = profile.language_preference if profile else "en"
    return lang if lang in SUPPORTED_LANGUAGES else "en"


async def assemble_reviews(
    session: AsyncSession,
    *,
    school_id: str,
    review_date: date,
    clusters: list[ClassifiedCluster],
    minis: list[dict[str, Any]],
) -> list[LectureReview]:
    """Upsert one review card per GSO that has qualifying clusters (T-200 #1/#4).

    Idempotent per ``(gso_id, review_date)``: a re-run refreshes the snapshot
    and summary of a card the teacher hasn't touched yet, and leaves an
    engaged card alone.
    """
    mini_by_cluster = {
        str(m["cluster_ref"]): str(m["lecture_id"])
        for m in minis
        if m.get("status") == "generated" and m.get("lecture_id")
    }
    by_gso: dict[str, list[ReviewClusterSnapshot]] = defaultdict(list)
    for cluster in clusters:
        if not cluster.gso_id:
            continue
        snap = build_snapshot(cluster, mini_by_cluster.get(cluster.cluster_ref))
        if snap is not None:
            by_gso[cluster.gso_id].append(snap)

    reviews: list[LectureReview] = []
    now = datetime.now(timezone.utc)
    for gso_id, snaps in by_gso.items():
        # Critical first, then by size — the card's column order (Flow 7 §3.3).
        snaps.sort(key=lambda s: (s.column != "critical", -s.question_count))
        # The review is a child of the lecture most of the day's questions hit.
        weights: Counter[str] = Counter()
        for s in snaps:
            weights[s.lecture_id] += s.question_count
        primary_lecture_id = weights.most_common(1)[0][0]
        lecture = await session.get(SchoolLecture, primary_lecture_id)
        if lecture is None or lecture.school_id != school_id:
            logger.warning(
                "review_assembly_lecture_missing", gso_id=gso_id, lecture_id=primary_lecture_id
            )
            continue

        existing = (
            await session.execute(
                select(LectureReview).where(
                    LectureReview.gso_id == gso_id,
                    LectureReview.review_date == review_date,
                )
            )
        ).scalar_one_or_none()
        if existing is not None and not existing.pending_action:
            reviews.append(existing)
            continue

        label = await _offering_label(session, gso_id)
        topic = lecture.topic or lecture.title
        language = await _teacher_language(session, lecture.teacher_user_id)
        summary = await generate_summary(
            snaps, offering_label=label, lecture_topic=topic, target_language=language
        )
        # T-202: coaching question about the teacher's own practice (optional).
        reflective = await generate_reflective_prompt(
            snaps, offering_label=label, lecture_topic=topic, target_language=language
        )
        mini_id = next((s.mini_lecture_id for s in snaps if s.mini_lecture_id), None)
        payload = [s.model_dump(mode="json") for s in snaps]

        review = existing or LectureReview(
            lecture_id=lecture.id, gso_id=gso_id, review_date=review_date
        )
        review.ai_summary = summary
        review.reflective_prompt = reflective
        review.clusters_jsonb = payload
        review.mini_lecture_id = mini_id
        review.generated_at = now
        review.pending_action = True
        review.status = LectureReviewStatus.PENDING
        if existing is None:
            session.add(review)
        reviews.append(review)

    await session.commit()
    logger.info(
        "review_assembly_complete",
        school_id=school_id,
        review_date=review_date.isoformat(),
        review_count=len(reviews),
    )
    return reviews


async def _schools_with_questions(session: AsyncSession, review_date: date) -> set[str]:
    start_utc, end_utc = karachi_day_bounds(review_date)
    result = await session.execute(
        select(SchoolStudentEvent.tenant_id)
        .join(SchoolLecture, SchoolLecture.id == SchoolStudentEvent.lecture_id)
        .where(
            SchoolStudentEvent.tenant_type == StudentEventTenantType.SCHOOL,
            SchoolStudentEvent.event_type.in_(QUESTION_EVENT_TYPES),
            SchoolStudentEvent.occurred_at >= start_utc,
            SchoolStudentEvent.occurred_at < end_utc,
            SchoolLecture.grade_subject_offering_id.is_not(None),
        )
        .distinct()
    )
    return {str(v) for v in result.scalars().all() if v}


async def _schools_with_reviews(session: AsyncSession, review_date: date) -> set[str]:
    result = await session.execute(
        select(SchoolLecture.school_id)
        .join(LectureReview, LectureReview.lecture_id == SchoolLecture.id)
        .where(
            LectureReview.review_date == review_date,
            LectureReview.generated_at.is_not(None),
        )
        .distinct()
    )
    return {str(v) for v in result.scalars().all() if v}


async def check_sla(session: AsyncSession, *, review_date: date) -> list[str]:
    """05:00 check: schools that had questions but no assembled card (T-200 #2).

    A school whose questions produced no qualifying cluster also has no card;
    it is reported too — at 05:00 the system cannot tell "nothing to review"
    from "pipeline still running", and the alert is a nudge for the Platform
    Admin to look, not an incident by itself.
    """
    missing = sorted(
        await _schools_with_questions(session, review_date)
        - await _schools_with_reviews(session, review_date)
    )
    if not missing:
        logger.info("review_sla_met", review_date=review_date.isoformat())
        return []
    await notify_all_platform_admins(
        session,
        template_key=SLA_BREACH_TEMPLATE,
        params={"count": str(len(missing)), "date": review_date.isoformat()},
        metadata={"review_date": review_date.isoformat(), "school_ids": missing},
    )
    await audit(
        session=session,
        action=REVIEW_SLA_BREACHED,
        target_type="review_date",
        target_id=review_date.isoformat(),
        metadata={"school_ids": missing},
    )
    await session.commit()
    logger.warning(
        "review_sla_breached", review_date=review_date.isoformat(), school_count=len(missing)
    )
    return missing


async def notify_ready_reviews(
    session: AsyncSession, *, review_date: date, now: datetime | None = None
) -> int:
    """06:00 dispatch: notify each teacher once per assembled card (T-200 #3).

    Refuses to send before 06:00 Karachi on the morning after ``review_date``
    even if the beat (or a manual run) fires early.
    """
    current = now or datetime.now(timezone.utc)
    if current < notify_not_before(review_date):
        logger.info(
            "review_notify_too_early",
            review_date=review_date.isoformat(),
            now=current.isoformat(),
        )
        return 0

    result = await session.execute(
        select(LectureReview, SchoolLecture)
        .join(SchoolLecture, SchoolLecture.id == LectureReview.lecture_id)
        .where(
            LectureReview.review_date == review_date,
            LectureReview.generated_at.is_not(None),
            LectureReview.notified_at.is_(None),
        )
    )
    sent = 0
    for review, lecture in result.all():
        try:
            recipient = await _resolve_recipient(session, lecture.teacher_user_id)
            if recipient is not None:
                authentik_id, locale = recipient
                await notify_lecture_event(
                    session=session,
                    template_key=REVIEW_READY_TEMPLATE,
                    recipient_user_id=authentik_id,
                    school_id=lecture.school_id,
                    locale=locale,
                    params={"topic": lecture.topic or lecture.title},
                    metadata={"review_id": review.id, "lecture_id": lecture.id},
                )
                sent += 1
        except Exception as exc:
            # Best-effort per teacher: one failed delivery must not stop the rest.
            logger.warning("review_notify_failed", review_id=review.id, error=str(exc))
            continue
        review.notified_at = current
    await session.commit()
    logger.info("review_notify_dispatched", review_date=review_date.isoformat(), sent=sent)
    return sent
