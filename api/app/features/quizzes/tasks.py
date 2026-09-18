"""Celery tasks for per-student quiz generation (T-143).

Queue: ``ml`` (ARCH §10.2 — four locked queues). LLM task id: ``quiz_gen``
(ARCH §8.4). One task per student — never serial fan-out in a single task.
"""

from __future__ import annotations

from typing import Any

import structlog

from app.db.celery_async import run_db
from app.tasks.base import tenant_task

logger = structlog.get_logger(__name__)

SOFT_TIME_LIMIT_SECONDS = 120
HARD_TIME_LIMIT_SECONDS = 150


@tenant_task(
    queue="ml",
    name="quizzes.generate_quiz_for_student",
    bind=True,
    max_retries=2,
    default_retry_delay=20,
    soft_time_limit=SOFT_TIME_LIMIT_SECONDS,
    time_limit=HARD_TIME_LIMIT_SECONDS,
)
def generate_quiz_for_student(
    self: Any,
    lecture_id: str,
    school_id: str,
    student_user_id: str,
    lecture_version_id: str | None = None,
) -> dict[str, object]:
    """Generate one calibrated quiz for a single student (parallel worker)."""
    from celery.exceptions import SoftTimeLimitExceeded

    logger.info(
        "quiz_gen_task_started",
        lecture_id=lecture_id,
        school_id=school_id,
        student_user_id=student_user_id,
    )
    try:
        quiz_id = run_db(
            lambda session: _run(
                session,
                lecture_id=lecture_id,
                school_id=school_id,
                student_user_id=student_user_id,
                lecture_version_id=lecture_version_id,
            )
        )
        return {"quiz_id": quiz_id, "student_user_id": student_user_id}
    except SoftTimeLimitExceeded:
        logger.error(
            "quiz_gen_task_timeout",
            lecture_id=lecture_id,
            student_user_id=student_user_id,
        )
        raise
    except Exception as exc:
        logger.exception(
            "quiz_gen_task_failed",
            lecture_id=lecture_id,
            student_user_id=student_user_id,
            error=str(exc),
        )
        raise


async def _run(
    session: Any,
    *,
    lecture_id: str,
    school_id: str,
    student_user_id: str,
    lecture_version_id: str | None,
) -> str | None:
    from app.features.quizzes.generation import run_quiz_generation_for_student

    return await run_quiz_generation_for_student(
        session,
        lecture_id=lecture_id,
        school_id=school_id,
        student_user_id=student_user_id,
        lecture_version_id=lecture_version_id,
    )


@tenant_task(
    queue="ml",
    name="quizzes.generate_for_late_enrollment",
    bind=True,
    max_retries=2,
    default_retry_delay=20,
    soft_time_limit=SOFT_TIME_LIMIT_SECONDS,
    time_limit=HARD_TIME_LIMIT_SECONDS,
)
def generate_for_late_enrollment(
    self: Any,
    school_id: str,
    student_user_id: str,
    grade_subject_offering_id: str,
) -> dict[str, object]:
    """T-148: generate quizzes for already-published lectures after late enroll."""
    from app.features.quizzes.late_enrollment import run_late_enrollment_quiz_generation

    count = run_db(
        lambda session: run_late_enrollment_quiz_generation(
            session,
            school_id=school_id,
            student_user_id=student_user_id,
            grade_subject_offering_id=grade_subject_offering_id,
        )
    )
    return {"quizzes_enqueued": count, "student_user_id": student_user_id}
