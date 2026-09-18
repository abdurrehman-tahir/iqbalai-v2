"""Independent-tenant lecture generation notification helpers (T-126).

Mirrors ``lecture_notifications.py`` for the independent schema: the teacher
IS an ``IndependentUser`` directly (no separate profile row for locale — the
language preference lives on the user row itself), and there is no
``school_id`` to scope by (``None`` is the correct, already-supported value —
see ``infrastructure/notifications/lectures.py``).
"""

from __future__ import annotations

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.independent_users.models import IndependentUser
from app.features.independent_users.repository import IndependentUserRepository
from app.features.lectures.models import IndependentLecture
from app.infrastructure.notifications.lectures import notify_lecture_event

logger = structlog.get_logger(__name__)


async def _resolve_recipient(
    session: AsyncSession, teacher_user_id: str | None
) -> IndependentUser | None:
    if not teacher_user_id:
        return None
    return await IndependentUserRepository(session).get_by_id(teacher_user_id)


async def notify_generation_complete(session: AsyncSession, *, lecture: IndependentLecture) -> None:
    try:
        user = await _resolve_recipient(session, lecture.teacher_user_id)
        if user is None:
            return
        await notify_lecture_event(
            session=session,
            template_key="lectures.generation_complete",
            recipient_user_id=user.authentik_id,
            school_id=None,
            locale=user.language_preference,
            params={"topic": lecture.topic},
            metadata={"lecture_id": lecture.id},
        )
    except Exception as exc:  # best-effort — mirrors lecture_notifications.py
        logger.warning(
            "independent_lecture_generation_complete_notify_failed",
            lecture_id=lecture.id,
            error=str(exc),
        )


async def notify_generation_failed(
    session: AsyncSession, *, lecture: IndependentLecture, error: str
) -> None:
    try:
        user = await _resolve_recipient(session, lecture.teacher_user_id)
        if user is None:
            return
        await notify_lecture_event(
            session=session,
            template_key="lectures.generation_failed",
            recipient_user_id=user.authentik_id,
            school_id=None,
            locale=user.language_preference,
            params={"topic": lecture.topic},
            metadata={"lecture_id": lecture.id, "error": error[:500]},
        )
    except Exception as exc:  # best-effort — mirrors lecture_notifications.py
        logger.warning(
            "independent_lecture_generation_failed_notify_failed",
            lecture_id=lecture.id,
            error=str(exc),
        )


async def notify_generation_timeout(session: AsyncSession, *, lecture: IndependentLecture) -> None:
    try:
        user = await _resolve_recipient(session, lecture.teacher_user_id)
        if user is None:
            return
        await notify_lecture_event(
            session=session,
            template_key="lectures.generation_timeout",
            recipient_user_id=user.authentik_id,
            school_id=None,
            locale=user.language_preference,
            params={"topic": lecture.topic},
            metadata={"lecture_id": lecture.id},
        )
    except Exception as exc:  # best-effort — mirrors lecture_notifications.py
        logger.warning(
            "independent_lecture_generation_timeout_notify_failed",
            lecture_id=lecture.id,
            error=str(exc),
        )
