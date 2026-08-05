"""Celery task: independent lecture generation — T-125.

Queue ``ml`` (LLM + retrieval), mirrors ``tasks.py``'s ``generate_lecture``.
No WS stream to notify on timeout/failure (this variant has no live token
relay) — the frontend polls lecture status instead, so a failure just needs
the lecture's own ``status`` column updated.

Uses the plain ``@celery_app.task`` decorator, not ``@tenant_task``: the
latter hard-requires a ``school_id`` parameter (it's specifically for
school-tenant RLS scoping, ARCH §10.4) which doesn't exist for independent
lectures. Matches the established independent-schema task precedent
(``library.independent_personal_tasks.ingest_independent_personal_content``).
"""

from __future__ import annotations

from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.celery_async import run_db
from app.features.lectures.models import IndependentLecture, LectureStatus
from app.infrastructure.celery.celery_app import celery_app

logger = structlog.get_logger(__name__)

SOFT_TIME_LIMIT_SECONDS = 300
HARD_TIME_LIMIT_SECONDS = 360


@celery_app.task(  # type: ignore[misc]
    name="lectures.generate_independent_lecture",
    queue="ml",
    bind=True,
    max_retries=1,
    default_retry_delay=30,
    soft_time_limit=SOFT_TIME_LIMIT_SECONDS,
    time_limit=HARD_TIME_LIMIT_SECONDS,
)
def generate_independent_lecture(
    self: Any,
    lecture_id: str,
    user_id: str,
    topic: str,
    reference_content_ids: list[str],
    teaching_mode: str,
    target_language: str = "en",
) -> dict[str, object]:
    """Run reference-only generation; on soft timeout mark lecture timed_out."""
    from celery.exceptions import (  # type: ignore[import-untyped]
        SoftTimeLimitExceeded,
        TimeLimitExceeded,
    )

    logger.info(
        "independent_lecture_generate_task_started",
        lecture_id=lecture_id,
        user_id=user_id,
        teaching_mode=teaching_mode,
    )
    try:
        version_id = run_db(
            lambda session: _run_generation(
                session,
                lecture_id=lecture_id,
                user_id=user_id,
                topic=topic,
                reference_content_ids=list(reference_content_ids),
                teaching_mode=teaching_mode,
                target_language=target_language,
            )
        )
        return {"lecture_id": lecture_id, "version_id": version_id, "status": "generated_v1"}
    except (SoftTimeLimitExceeded, TimeLimitExceeded):
        run_db(lambda session: _mark_status(session, lecture_id, user_id, LectureStatus.TIMED_OUT))
        logger.warning(
            "independent_lecture_generate_timed_out",
            lecture_id=lecture_id,
            user_id=user_id,
            soft_time_limit=SOFT_TIME_LIMIT_SECONDS,
        )
        return {"lecture_id": lecture_id, "status": "timed_out"}
    except Exception as exc:
        run_db(lambda session: _mark_status(session, lecture_id, user_id, LectureStatus.FAILED))
        logger.error(
            "independent_lecture_generate_failed",
            lecture_id=lecture_id,
            user_id=user_id,
            error=str(exc),
        )
        raise


async def _run_generation(
    session: AsyncSession,
    *,
    lecture_id: str,
    user_id: str,
    topic: str,
    reference_content_ids: list[str],
    teaching_mode: str,
    target_language: str,
) -> str:
    from app.features.lectures.independent_generation import run_independent_lecture_generation

    return await run_independent_lecture_generation(
        session,
        lecture_id=lecture_id,
        user_id=user_id,
        topic=topic,
        reference_content_ids=reference_content_ids,
        teaching_mode=teaching_mode,
        target_language=target_language,
    )


async def _mark_status(
    session: AsyncSession,
    lecture_id: str,
    user_id: str,
    status: LectureStatus,
) -> None:
    lecture = await session.get(IndependentLecture, lecture_id)
    if lecture is None or lecture.teacher_user_id != user_id:
        return
    lecture.status = status
    await session.commit()
