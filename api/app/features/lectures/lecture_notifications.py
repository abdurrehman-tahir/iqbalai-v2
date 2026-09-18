"""School-tenant lecture generation notification helpers (T-126).

Fired from the Celery generation task / pipeline after the lecture's status
has already been committed. Best-effort: a notification failure must never
flip a successfully-generated lecture back to failed, or mask the real
failure/timeout status transition that already happened — so every helper
here catches and logs rather than raising, matching the established pattern
in ``infrastructure/notifications/framework.py``'s ``notify_platform_admins``.
"""

from __future__ import annotations

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.lectures.models import SchoolLecture
from app.features.teacher_onboarding.repository import TeacherProfileRepository
from app.features.users.repository import UserRepository
from app.infrastructure.notifications.lectures import notify_lecture_event
from app.infrastructure.notifications.templates.lectures import DEFAULT_LOCALE

logger = structlog.get_logger(__name__)


async def _resolve_recipient(
    session: AsyncSession, teacher_user_id: str | None
) -> tuple[str, str] | None:
    """Return (authentik_id, locale) for the lecture's teacher, or None if unresolvable."""
    if not teacher_user_id:
        return None
    user = await UserRepository(session).get_by_id(teacher_user_id)
    if user is None:
        return None
    profile = await TeacherProfileRepository(session).get_by_user_id(teacher_user_id)
    locale = profile.language_preference if profile is not None else DEFAULT_LOCALE
    return user.authentik_id, locale


async def notify_generation_complete(session: AsyncSession, *, lecture: SchoolLecture) -> None:
    try:
        recipient = await _resolve_recipient(session, lecture.teacher_user_id)
        if recipient is None:
            return
        authentik_id, locale = recipient
        await notify_lecture_event(
            session=session,
            template_key="lectures.generation_complete",
            recipient_user_id=authentik_id,
            school_id=lecture.school_id,
            locale=locale,
            params={"topic": lecture.topic},
            metadata={"lecture_id": lecture.id},
        )
    except Exception as exc:  # best-effort — see module docstring
        logger.warning(
            "lecture_generation_complete_notify_failed", lecture_id=lecture.id, error=str(exc)
        )


async def notify_generation_failed(
    session: AsyncSession, *, lecture: SchoolLecture, error: str
) -> None:
    try:
        recipient = await _resolve_recipient(session, lecture.teacher_user_id)
        if recipient is None:
            return
        authentik_id, locale = recipient
        await notify_lecture_event(
            session=session,
            template_key="lectures.generation_failed",
            recipient_user_id=authentik_id,
            school_id=lecture.school_id,
            locale=locale,
            params={"topic": lecture.topic},
            metadata={"lecture_id": lecture.id, "error": error[:500]},
        )
    except Exception as exc:  # best-effort — see module docstring
        logger.warning(
            "lecture_generation_failed_notify_failed", lecture_id=lecture.id, error=str(exc)
        )


async def notify_generation_timeout(session: AsyncSession, *, lecture: SchoolLecture) -> None:
    try:
        recipient = await _resolve_recipient(session, lecture.teacher_user_id)
        if recipient is None:
            return
        authentik_id, locale = recipient
        await notify_lecture_event(
            session=session,
            template_key="lectures.generation_timeout",
            recipient_user_id=authentik_id,
            school_id=lecture.school_id,
            locale=locale,
            params={"topic": lecture.topic},
            metadata={"lecture_id": lecture.id},
        )
    except Exception as exc:  # best-effort — see module docstring
        logger.warning(
            "lecture_generation_timeout_notify_failed", lecture_id=lecture.id, error=str(exc)
        )
