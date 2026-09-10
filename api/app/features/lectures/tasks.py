"""Celery tasks: lecture generation (T-116) + voice-audio retention purge (T-121).

Generation queue: ``ml`` (LLM + retrieval). soft_time_limit = 5 minutes.
DB via ``run_db`` (disposable engine) — never the API session factory.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any

import structlog
from celery import shared_task
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.celery_async import run_db
from app.features.audit.actions import LECTURE_GENERATION_FAILED, LECTURE_GENERATION_TIMED_OUT
from app.features.lectures.events import (
    LECTURE_GENERATION_FAILED as LECTURE_GENERATION_FAILED_EVENT,
)
from app.features.lectures.events import (
    LECTURE_GENERATION_TIMED_OUT as LECTURE_GENERATION_TIMED_OUT_EVENT,
)
from app.features.lectures.events import publish_lecture_event
from app.features.lectures.generation_stream import mark_failed
from app.features.lectures.lecture_notifications import (
    notify_generation_failed,
    notify_generation_timeout,
)
from app.features.lectures.models import LectureStatus, SchoolLecture
from app.infrastructure.audit.log import audit
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
        run_db(lambda session: _handle_generation_timeout(session, lecture_id, school_id))
        asyncio.run(mark_failed(lecture_id, reason="timed_out"))
        logger.warning(
            "lecture_generate_timed_out",
            lecture_id=lecture_id,
            school_id=school_id,
            soft_time_limit=SOFT_TIME_LIMIT_SECONDS,
        )
        return {"lecture_id": lecture_id, "status": "timed_out"}
    except Exception as exc:
        # Captured before the lambda: `except ... as exc` deletes `exc` when the
        # block exits, so a closure referencing it directly is fragile.
        error_message = str(exc)
        run_db(
            lambda session: _handle_generation_failure(
                session, lecture_id, school_id, error_message
            )
        )
        asyncio.run(mark_failed(lecture_id, reason=error_message))
        logger.error(
            "lecture_generate_failed",
            lecture_id=lecture_id,
            school_id=school_id,
            error=error_message,
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


async def _handle_generation_timeout(
    session: AsyncSession, lecture_id: str, school_id: str
) -> None:
    lecture = await session.get(SchoolLecture, lecture_id)
    if lecture is None or lecture.school_id != school_id:
        return
    lecture.status = LectureStatus.TIMED_OUT
    await session.commit()

    await audit(
        session=session,
        action=LECTURE_GENERATION_TIMED_OUT,
        actor_id=lecture.teacher_user_id,
        actor_role="teacher",
        target_type="lecture",
        target_id=lecture_id,
        school_id=school_id,
    )
    await notify_generation_timeout(session, lecture=lecture)
    await publish_lecture_event(
        event_type=LECTURE_GENERATION_TIMED_OUT_EVENT,
        payload={
            "lecture_id": lecture_id,
            "school_id": school_id,
            "teacher_user_id": lecture.teacher_user_id,
            "tenant_type": "school",
        },
    )


async def _handle_generation_failure(
    session: AsyncSession, lecture_id: str, school_id: str, error: str
) -> None:
    lecture = await session.get(SchoolLecture, lecture_id)
    if lecture is None or lecture.school_id != school_id:
        return
    lecture.status = LectureStatus.FAILED
    await session.commit()

    await audit(
        session=session,
        action=LECTURE_GENERATION_FAILED,
        actor_id=lecture.teacher_user_id,
        actor_role="teacher",
        target_type="lecture",
        target_id=lecture_id,
        school_id=school_id,
        metadata={"error": error[:500]},
    )
    await notify_generation_failed(session, lecture=lecture, error=error)
    await publish_lecture_event(
        event_type=LECTURE_GENERATION_FAILED_EVENT,
        payload={
            "lecture_id": lecture_id,
            "school_id": school_id,
            "teacher_user_id": lecture.teacher_user_id,
            "tenant_type": "school",
            "error": error[:500],
        },
    )


@tenant_task(
    queue="ml",
    name="lectures.generate_teacher_tips",
    bind=True,
    max_retries=1,
    default_retry_delay=30,
    soft_time_limit=90,
    time_limit=120,
)
def generate_lecture_teacher_tips(
    self: Any,
    lecture_id: str,
    school_id: str,
    version_id: str,
    topic: str,
    target_language: str = "en",
) -> dict[str, object]:
    """T-124 (#28, #41): supplementary teacher-facing tips — never fails the lecture.

    Its own short time limit (well under the main task's 5 minutes) and its own
    broad except-and-log: a slow or errored tips call must never flip the
    already-successful lecture back to FAILED/TIMED_OUT.
    """
    logger.info("lecture_teacher_tips_task_started", lecture_id=lecture_id, version_id=version_id)
    try:
        run_db(
            lambda session: _run_teacher_tips_generation(
                session,
                lecture_id=lecture_id,
                school_id=school_id,
                version_id=version_id,
                topic=topic,
                target_language=target_language,
            )
        )
        return {"lecture_id": lecture_id, "version_id": version_id, "status": "ready"}
    except Exception as exc:
        logger.warning(
            "lecture_teacher_tips_task_failed",
            lecture_id=lecture_id,
            version_id=version_id,
            error=str(exc),
        )
        return {"lecture_id": lecture_id, "version_id": version_id, "status": "failed"}


async def _run_teacher_tips_generation(
    session: AsyncSession,
    *,
    lecture_id: str,
    school_id: str,
    version_id: str,
    topic: str,
    target_language: str,
) -> None:
    from app.features.lectures.generation import run_teacher_tips_generation

    await run_teacher_tips_generation(
        session,
        lecture_id=lecture_id,
        school_id=school_id,
        version_id=version_id,
        topic=topic,
        target_language=target_language,
    )


@shared_task(  # type: ignore[misc]
    name="lectures.purge_voice_audio",
    queue="default",
    soft_time_limit=120,
    time_limit=180,
)
def purge_expired_voice_audio() -> dict[str, object]:
    """Delete raw voice-turn audio past retention (T-121 #25, flow-5 §6 Limits).

    System-wide sweep across BOTH schemas (no single school_id — plain
    @shared_task, not @tenant_task, per stack-enforcer's system-task
    opt-out). T-125 added independent voice sessions with the same
    retention requirement, so this purges both. Transcripts
    (``lecture_voice_turns`` rows) are kept indefinitely — only the MinIO
    object + the row's ``audio_storage_key`` pointer are cleared.
    """
    return run_db(_purge_expired_voice_audio_async)


async def _purge_expired_voice_audio_async(session: AsyncSession) -> dict[str, object]:
    from app.config import get_settings
    from app.features.lectures.independent_repository import (
        IndependentLectureVoiceTurnRepository,
    )
    from app.features.lectures.repository import LectureVoiceTurnRepository
    from app.infrastructure.storage.client import delete_object

    settings = get_settings()
    cutoff = datetime.now(timezone.utc) - timedelta(hours=settings.VOICE_AUDIO_RETENTION_HOURS)

    purged = 0

    school_repo = LectureVoiceTurnRepository(session)
    for school_turn in await school_repo.list_with_unpurged_audio_older_than(cutoff):
        if school_turn.audio_storage_key:
            delete_object("audio", school_turn.audio_storage_key)
        await school_repo.mark_audio_purged(school_turn)
        purged += 1

    independent_repo = IndependentLectureVoiceTurnRepository(session)
    for independent_turn in await independent_repo.list_with_unpurged_audio_older_than(cutoff):
        if independent_turn.audio_storage_key:
            delete_object("audio", independent_turn.audio_storage_key)
        await independent_repo.mark_audio_purged(independent_turn)
        purged += 1

    logger.info("voice_audio_purge_complete", purged_count=purged, cutoff=cutoff.isoformat())
    return {"purged_count": purged}
