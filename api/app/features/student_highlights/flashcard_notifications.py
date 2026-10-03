"""Nightly flashcard batch notification — T-193 (flow-6 §7, ARCH §10.6 / §9.21).

One in-app ``self_study.flashcards_added_batch`` notification per student per
night (never per card), counting the flashcards auto-created from that
student's highlights in a fixed 24h window ending at the scheduled run time
(18:15 UTC = 23:15 PKT). The window marker is stored in the notification
metadata, so a retried / duplicated run never notifies a student twice.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.notifications.models import Notification
from app.features.student_highlights.models import FlashcardSourceType, SchoolStudentFlashcard
from app.features.student_onboarding.models import StudentProfile
from app.features.users.models import User
from app.infrastructure.notifications.self_study import notify_self_study_event

logger = structlog.get_logger(__name__)

TEMPLATE_KEY = "self_study.flashcards_added_batch"
RUN_HOUR_UTC = 18
RUN_MINUTE_UTC = 15


def batch_window(now: datetime) -> tuple[datetime, datetime]:
    """[start, end) — end is the latest scheduled boundary at or before ``now``."""
    end = now.astimezone(timezone.utc).replace(
        hour=RUN_HOUR_UTC, minute=RUN_MINUTE_UTC, second=0, microsecond=0
    )
    if end > now:
        end -= timedelta(days=1)
    return end - timedelta(days=1), end


async def _already_sent(session: AsyncSession, recipient: str, marker: str) -> bool:
    result = await session.execute(
        select(func.count())
        .select_from(Notification)
        .where(
            Notification.recipient_user_id == recipient,
            Notification.template_key == TEMPLATE_KEY,
            Notification.metadata_json.contains(marker),
        )
    )
    return int(result.scalar_one()) > 0


async def send_flashcard_batch(session: AsyncSession, *, now: datetime | None = None) -> int:
    """Notify every student who got new flashcards in the window. Returns sent count."""
    start, end = batch_window(now or datetime.now(timezone.utc))
    rows = (
        await session.execute(
            select(
                User.authentik_id,
                User.school_id,
                StudentProfile.language_preference,
                func.count(SchoolStudentFlashcard.id),
            )
            .join(User, User.id == SchoolStudentFlashcard.student_user_id)
            .outerjoin(StudentProfile, StudentProfile.user_id == User.id)
            .where(
                SchoolStudentFlashcard.created_at >= start,
                SchoolStudentFlashcard.created_at < end,
                SchoolStudentFlashcard.deleted_at.is_(None),
                SchoolStudentFlashcard.source_type == FlashcardSourceType.HIGHLIGHT,
                User.deleted_at.is_(None),
            )
            .group_by(User.authentik_id, User.school_id, StudentProfile.language_preference)
        )
    ).all()

    marker = f'"window_end": "{end.isoformat()}"'
    sent = 0
    for authentik_id, school_id, language, count in rows:
        if await _already_sent(session, authentik_id, marker):
            continue
        try:
            await notify_self_study_event(
                session=session,
                template_key=TEMPLATE_KEY,
                recipient_user_id=authentik_id,
                school_id=school_id,
                locale=language or "en",
                params={"count": str(int(count))},
                metadata={"window_end": end.isoformat(), "count": int(count)},
            )
            sent += 1
        except Exception as exc:  # best-effort per student; one failure never blocks the rest
            logger.warning("flashcard_batch_notify_failed", error=str(exc))
    logger.info(
        "flashcard_batch_notifications_sent",
        sent=sent,
        window_start=start.isoformat(),
        window_end=end.isoformat(),
    )
    return sent
