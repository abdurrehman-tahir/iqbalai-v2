"""Celery task: Pattern S dual-RAG lecture generation — T-116.

Queue: ``ml`` (LLM + retrieval). soft_time_limit = 5 minutes.
DB via ``run_db`` (disposable engine) — never the API session factory.
"""

from __future__ import annotations

import asyncio
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.celery_async import run_db
from app.features.lectures.generation_stream import mark_failed
from app.features.lectures.models import LectureStatus, SchoolLecture
from app.tasks.base import tenant_task

logger = structlog.get_logger(__name__)

SOFT_TIME_LIMIT_SECONDS = 300
HARD_TIME_LIMIT_SECONDS = 360


@tenant_task(
    queue="ml",
    name="lectures.generate_lecture",
    bind=True,
    max_retries=1,
    default_retry_delay=30,
    soft_time_limit=SOFT_TIME_LIMIT_SECONDS,
    time_limit=HARD_TIME_LIMIT_SECONDS,
)
def generate_lecture(
    self: Any,
    lecture_id: str,
    school_id: str,
    topic: str,
    curriculum_id: str,
    reference_book_ids: list[str],
    teaching_mode: str,
    teacher_user_id: str,
    target_language: str = "en",
) -> dict[str, object]:
    """Run dual-RAG generation; on soft timeout mark lecture timed_out."""
    from celery.exceptions import (  # type: ignore[import-untyped]
        SoftTimeLimitExceeded,
        TimeLimitExceeded,
    )

    logger.info(
        "lecture_generate_task_started",
        lecture_id=lecture_id,
        school_id=school_id,
        teaching_mode=teaching_mode,
    )
    try:
        version_id = run_db(
            lambda session: _run_generation(
                session,
                lecture_id=lecture_id,
                school_id=school_id,
                topic=topic,
                curriculum_id=curriculum_id,
                reference_book_ids=list(reference_book_ids),
                teaching_mode=teaching_mode,
                teacher_user_id=teacher_user_id,
                target_language=target_language,
            )
        )
        return {"lecture_id": lecture_id, "version_id": version_id, "status": "generated_v1"}
    except (SoftTimeLimitExceeded, TimeLimitExceeded):
        run_db(
            lambda session: _mark_status(session, lecture_id, school_id, LectureStatus.TIMED_OUT)
        )
        asyncio.run(mark_failed(lecture_id, reason="timed_out"))
        logger.warning(
            "lecture_generate_timed_out",
            lecture_id=lecture_id,
            school_id=school_id,
            soft_time_limit=SOFT_TIME_LIMIT_SECONDS,
        )
        # Full teacher notification templates land in T-126; structured log is the notify hook.
        return {"lecture_id": lecture_id, "status": "timed_out"}
    except Exception as exc:
        run_db(lambda session: _mark_status(session, lecture_id, school_id, LectureStatus.FAILED))
        asyncio.run(mark_failed(lecture_id, reason=str(exc)))
        logger.error(
            "lecture_generate_failed",
            lecture_id=lecture_id,
            school_id=school_id,
            error=str(exc),
        )
        raise


async def _run_generation(
    session: AsyncSession,
    *,
    lecture_id: str,
    school_id: str,
    topic: str,
    curriculum_id: str,
    reference_book_ids: list[str],
    teaching_mode: str,
    teacher_user_id: str,
    target_language: str,
) -> str:
    from app.features.lectures.generation import run_lecture_generation

    return await run_lecture_generation(
        session,
        lecture_id=lecture_id,
        school_id=school_id,
        topic=topic,
        curriculum_id=curriculum_id,
        reference_book_ids=reference_book_ids,
        teaching_mode=teaching_mode,
        teacher_user_id=teacher_user_id,
        target_language=target_language,
    )


async def _mark_status(
    session: AsyncSession,
    lecture_id: str,
    school_id: str,
    status: LectureStatus,
) -> None:
    lecture = await session.get(SchoolLecture, lecture_id)
    if lecture is None or lecture.school_id != school_id:
        return
    lecture.status = status
    await session.commit()
