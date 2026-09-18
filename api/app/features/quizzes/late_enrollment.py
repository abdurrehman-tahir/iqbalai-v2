"""Event-driven late-enrollment quiz generation (T-148).

Triggered by ``student.enrolled`` — NOT a Celery beat job.
Independent teachers are excluded (no school offering / auto-quiz skip).
"""

from __future__ import annotations

from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.lectures.models import LectureStatus, SchoolLecture
from app.features.offerings.repository import OfferingRepository
from app.features.quizzes.models import SchoolQuiz

logger = structlog.get_logger(__name__)


async def run_late_enrollment_quiz_generation(
    session: AsyncSession,
    *,
    school_id: str,
    student_user_id: str,
    grade_subject_offering_id: str,
) -> int:
    """Enqueue quiz generation for published lectures of this offering.

    Skips lectures that already have a quiz for this student (dedupe).
    Returns number of tasks enqueued.
    """
    from app.features.quizzes.tasks import generate_quiz_for_student

    lectures = (
        (
            await session.execute(
                select(SchoolLecture).where(
                    SchoolLecture.school_id == school_id,
                    SchoolLecture.grade_subject_offering_id == grade_subject_offering_id,
                    SchoolLecture.status == LectureStatus.PUBLISHED,
                    SchoolLecture.deleted_at.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )

    enqueued = 0
    for lecture in lectures:
        if lecture.current_version_id is None:
            continue
        existing = await session.execute(
            select(SchoolQuiz.id).where(
                SchoolQuiz.lecture_version_id == lecture.current_version_id,
                SchoolQuiz.student_user_id == student_user_id,
                SchoolQuiz.deleted_at.is_(None),
            )
        )
        if existing.scalar_one_or_none() is not None:
            logger.info(
                "late_enrollment_quiz_skip_duplicate",
                lecture_id=lecture.id,
                student_user_id=student_user_id,
            )
            continue

        generate_quiz_for_student.apply_async(
            kwargs={
                "lecture_id": lecture.id,
                "school_id": school_id,
                "student_user_id": student_user_id,
                "lecture_version_id": lecture.current_version_id,
            }
        )
        enqueued += 1

    logger.info(
        "late_enrollment_quiz_enqueued",
        student_user_id=student_user_id,
        offering_id=grade_subject_offering_id,
        count=enqueued,
    )
    return enqueued


async def enqueue_late_quizzes_for_grade_enrollment(
    session: AsyncSession,
    *,
    school_id: str,
    student_user_id: str,
    grade_id: str,
) -> int:
    """Fan out late-enrollment tasks across all active offerings of a grade."""
    from app.features.quizzes.tasks import generate_for_late_enrollment

    offerings = await OfferingRepository(session).list_by_grade(grade_id)
    total = 0
    for offering in offerings:
        generate_for_late_enrollment.apply_async(
            kwargs={
                "school_id": school_id,
                "student_user_id": student_user_id,
                "grade_subject_offering_id": offering.id,
            }
        )
        total += 1
    logger.info(
        "late_enrollment_grade_fanout",
        student_user_id=student_user_id,
        grade_id=grade_id,
        offerings=total,
    )
    return total


async def handle_student_enrolled_event(envelope: dict[str, Any]) -> None:
    """NATS consumer handler for ``student.enrolled`` (T-148).

    School-tenant only — independent enrollments never trigger auto-quiz.
    """
    if envelope.get("tenant_type") == "independent":
        logger.info("late_enrollment_skip_independent")
        return

    payload = envelope.get("payload") or {}
    school_id = str(payload.get("school_id") or envelope.get("tenant_id") or "")
    student_user_id = str(payload.get("student_user_id") or "")
    grade_id = str(payload.get("grade_id") or "")
    offering_id = payload.get("grade_subject_offering_id")

    if not school_id or not student_user_id:
        logger.warning("late_enrollment_event_incomplete", payload=payload)
        return

    from app.db.celery_async import run_db

    if offering_id:
        run_db(
            lambda session: run_late_enrollment_quiz_generation(
                session,
                school_id=school_id,
                student_user_id=student_user_id,
                grade_subject_offering_id=str(offering_id),
            )
        )
        return

    if not grade_id:
        logger.warning("late_enrollment_event_missing_grade", payload=payload)
        return

    run_db(
        lambda session: enqueue_late_quizzes_for_grade_enrollment(
            session,
            school_id=school_id,
            student_user_id=student_user_id,
            grade_id=grade_id,
        )
    )
