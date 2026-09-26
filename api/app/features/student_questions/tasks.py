"""Celery task: purge expired student_question_image uploads (T-166 / T-170).

Mirrors ``lectures.purge_voice_audio`` (T-121) — a system-wide sweep across
both schemas is unnecessary here (``student_question_image`` is school-only
per T-166's scope), so this is a plain ``@shared_task``, not ``@tenant_task``.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import structlog
from celery import shared_task
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.celery_async import run_db
from app.features.files.pipeline import list_expired_uploads, purge_expired_upload
from app.features.files.profiles import STUDENT_QUESTION_IMAGE

logger = structlog.get_logger(__name__)


@shared_task(  # type: ignore[misc]
    name="student_questions.purge_expired_question_images",
    queue="default",
    soft_time_limit=120,
    time_limit=180,
)
def purge_expired_question_images() -> dict[str, object]:
    """Delete ``student_question_image`` uploads past the 1-year retention.

    Deletes the MinIO object and soft-deletes the ``upload_records`` row once
    ``UploadProfile.retention_days`` (365) has elapsed since ``created_at``.
    Transcripts / question rows themselves are untouched — only the image
    object + its upload-record pointer are purged (mirrors the voice-audio
    purge's "keep the text, drop the raw media" pattern).
    """
    return run_db(_purge_expired_question_images_async)


async def _purge_expired_question_images_async(session: AsyncSession) -> dict[str, object]:
    retention_days = STUDENT_QUESTION_IMAGE.retention_days or 365
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)

    purged = 0
    for record in await list_expired_uploads(
        session, profile_name=STUDENT_QUESTION_IMAGE.name, cutoff=cutoff
    ):
        await purge_expired_upload(session, record)
        purged += 1

    logger.info(
        "student_question_image_purge_complete",
        purged_count=purged,
        cutoff=cutoff.isoformat(),
    )
    return {"purged_count": purged}
