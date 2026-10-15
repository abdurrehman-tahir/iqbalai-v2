"""Overnight question aggregation for next-day review — T-196 (Flow 7 §3.1).

Reads ``student_events`` for one school + Karachi calendar day, applies #72
share filter + school GSO lecture scope, and buckets by
``(lecture_id, paragraph_id, source_chunk_id)`` for T-197 clustering.

Natural idempotency: re-running the same ``(school_id, review_date)`` re-reads
the same durable events and rebuilds the same buckets (read-only; no writes).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.lectures.models import SchoolLecture
from app.features.schools.models import School
from app.features.student_events.models import SchoolStudentEvent, StudentEventTenantType
from app.features.student_mode.models import TeacherActivityShare, UserSettings
from app.infrastructure.events.subjects import STUDENT_LECTURE_QUESTION_ASKED

logger = structlog.get_logger(__name__)

KARACHI = ZoneInfo("Asia/Karachi")

# Dual-publish (T-173) may persist either the M-12 subject or the ARCH alias.
QUESTION_EVENT_TYPES: frozenset[str] = frozenset(
    {
        "student.question.asked",
        STUDENT_LECTURE_QUESTION_ASKED,
    }
)


@dataclass(frozen=True, slots=True)
class QuestionBucketKey:
    lecture_id: str
    paragraph_id: str | None
    source_chunk_id: str | None

    def as_tuple(self) -> tuple[str, str | None, str | None]:
        return (self.lecture_id, self.paragraph_id, self.source_chunk_id)

    def serialize(self) -> str:
        """Stable string key for JSON / Celery results."""
        return "|".join(
            [
                self.lecture_id,
                self.paragraph_id or "",
                self.source_chunk_id or "",
            ]
        )


def karachi_day_bounds(review_date: date) -> tuple[datetime, datetime]:
    """Return inclusive-start / exclusive-end UTC bounds for a Karachi calendar day."""
    start_local = datetime(review_date.year, review_date.month, review_date.day, tzinfo=KARACHI)
    end_local = start_local + timedelta(days=1)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)


def today_karachi() -> date:
    return datetime.now(KARACHI).date()


def _payload_str(payload: dict[str, Any], key: str) -> str | None:
    raw = payload.get(key)
    if raw is None:
        return None
    text = str(raw).strip()
    return text or None


def bucket_key_from_event(
    *, lecture_id: str | None, payload: dict[str, Any]
) -> QuestionBucketKey | None:
    resolved_lecture = lecture_id or _payload_str(payload, "lecture_id")
    if not resolved_lecture:
        return None
    return QuestionBucketKey(
        lecture_id=resolved_lecture,
        paragraph_id=_payload_str(payload, "paragraph_id"),
        source_chunk_id=_payload_str(payload, "source_chunk_id"),
    )


def _is_share_allowed(payload: dict[str, Any], private_user_ids: set[str], user_id: str) -> bool:
    """#72: exclude opted-out students.

    Prefer the event's ``teacher_share`` stamp (set at ask time). Fall back to
    current ``user_settings.teacher_activity_share == private``; missing settings
    default to share (Open Q12).
    """
    stamp = _payload_str(payload, "teacher_share")
    if stamp == TeacherActivityShare.PRIVATE.value:
        return False
    if stamp == TeacherActivityShare.SHARE.value:
        return True
    return user_id not in private_user_ids


async def list_active_school_ids(session: AsyncSession) -> list[str]:
    """Active (not soft-deleted) schools — fan-out targets for the nightly beat."""
    stmt: Select[tuple[str]] = (
        select(School.id).where(School.deleted_at.is_(None)).order_by(School.id.asc())
    )
    result = await session.execute(stmt)
    return [str(row[0]) for row in result.all()]


async def _private_user_ids(session: AsyncSession) -> set[str]:
    stmt = select(UserSettings.user_id).where(
        UserSettings.teacher_activity_share == TeacherActivityShare.PRIVATE,
        UserSettings.deleted_at.is_(None),
    )
    result = await session.execute(stmt)
    return {str(uid) for uid in result.scalars().all()}


async def _school_lecture_ids_with_gso(session: AsyncSession, school_id: str) -> set[str]:
    """Lectures in this school that sit on a Grade-Subject offering (teacher GSO scope)."""
    stmt = select(SchoolLecture.id).where(
        SchoolLecture.school_id == school_id,
        SchoolLecture.grade_subject_offering_id.is_not(None),
        SchoolLecture.deleted_at.is_(None),
    )
    result = await session.execute(stmt)
    return {str(lid) for lid in result.scalars().all()}


async def aggregate_school_day(
    session: AsyncSession,
    school_id: str,
    review_date: date,
) -> dict[str, list[dict[str, Any]]]:
    """Build question buckets for one school + Karachi day.

    Returns a map of serialized ``QuestionBucketKey`` → list of question payloads
    (deduped by ``question_id`` so dual-publish alias rows don't double-count).
    """
    start_utc, end_utc = karachi_day_bounds(review_date)
    lecture_ids = await _school_lecture_ids_with_gso(session, school_id)
    if not lecture_ids:
        logger.info(
            "review_aggregate_no_gso_lectures",
            school_id=school_id,
            review_date=review_date.isoformat(),
        )
        return {}

    private_users = await _private_user_ids(session)

    stmt = select(SchoolStudentEvent).where(
        SchoolStudentEvent.tenant_type == StudentEventTenantType.SCHOOL,
        SchoolStudentEvent.tenant_id == school_id,
        SchoolStudentEvent.event_type.in_(QUESTION_EVENT_TYPES),
        SchoolStudentEvent.occurred_at >= start_utc,
        SchoolStudentEvent.occurred_at < end_utc,
        SchoolStudentEvent.lecture_id.in_(lecture_ids),
    )
    result = await session.execute(stmt)
    events = list(result.scalars().all())

    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    seen_question_ids: set[str] = set()
    skipped_private = 0

    for event in events:
        payload = dict(event.event_payload_jsonb or {})
        if not _is_share_allowed(payload, private_users, event.user_id):
            skipped_private += 1
            continue
        key = bucket_key_from_event(lecture_id=event.lecture_id, payload=payload)
        if key is None:
            continue
        question_id = _payload_str(payload, "question_id") or event.id
        if question_id in seen_question_ids:
            continue
        seen_question_ids.add(question_id)
        item = {
            "event_id": event.id,
            "question_id": question_id,
            "user_id": event.user_id,
            "lecture_id": key.lecture_id,
            "paragraph_id": key.paragraph_id,
            "source_chunk_id": key.source_chunk_id,
            "question_text": payload.get("question_text"),
            "classification": payload.get("classification"),
            "occurred_at": event.occurred_at.isoformat(),
        }
        buckets[key.serialize()].append(item)

    logger.info(
        "review_aggregate_school_complete",
        school_id=school_id,
        review_date=review_date.isoformat(),
        bucket_count=len(buckets),
        question_count=len(seen_question_ids),
        skipped_private=skipped_private,
        event_rows=len(events),
    )
    return dict(buckets)
