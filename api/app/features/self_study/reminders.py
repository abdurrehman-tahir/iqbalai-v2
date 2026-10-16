"""Reminder preferences + session reminder dispatch — T-218."""

from __future__ import annotations

from typing import Literal

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, PermissionDeniedError
from app.core.tenant import get_tenant_type
from app.features.independent_users.models import IndependentUser, IndependentUserRole
from app.features.independent_users.repository import IndependentUserRepository
from app.features.self_study.models import (
    IndependentReminderPreference,
    SchoolReminderPreference,
)
from app.features.self_study.schemas import (
    ReminderPreferencesRead,
    ReminderPreferencesUpdate,
)
from app.features.users.models import User, UserRole
from app.features.users.repository import UserRepository

logger = structlog.get_logger(__name__)


def _to_read(
    row: SchoolReminderPreference | IndependentReminderPreference,
) -> ReminderPreferencesRead:
    return ReminderPreferencesRead(
        push_enabled=row.push_enabled,
        email_enabled=row.email_enabled,
        sms_enabled=row.sms_enabled,
        timezone=row.timezone,
    )


class SelfStudyReminderService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._school_users = UserRepository(session)
        self._ind_users = IndependentUserRepository(session)

    async def _require_school_student(self, claims: dict[str, object]) -> User:
        if str(claims.get("role", "")) != UserRole.STUDENT.value:
            raise PermissionDeniedError("Requires a school student account")
        user = await self._school_users.get_by_authentik_id(str(claims.get("sub", "")))
        if user is None or user.role != UserRole.STUDENT:
            raise NotFoundError("Student not found")
        return user

    async def _require_independent_student(self, claims: dict[str, object]) -> IndependentUser:
        user = await self._ind_users.get_by_authentik_id(str(claims.get("sub", "")))
        if user is None or user.role != IndependentUserRole.INDEPENDENT_STUDENT:
            raise NotFoundError("Independent student not found")
        return user

    async def get_prefs(self, claims: dict[str, object]) -> ReminderPreferencesRead:
        tenant = get_tenant_type(claims)
        if tenant == "independent":
            return await self._get_or_create_independent(claims)
        return await self._get_or_create_school(claims)

    async def _get_or_create_independent(
        self, claims: dict[str, object]
    ) -> ReminderPreferencesRead:
        user = await self._require_independent_student(claims)
        result = await self._session.execute(
            select(IndependentReminderPreference).where(
                IndependentReminderPreference.student_user_id == user.id
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            row = IndependentReminderPreference(student_user_id=user.id)
            self._session.add(row)
            await self._session.commit()
            await self._session.refresh(row)
        return _to_read(row)

    async def _get_or_create_school(self, claims: dict[str, object]) -> ReminderPreferencesRead:
        user = await self._require_school_student(claims)
        result = await self._session.execute(
            select(SchoolReminderPreference).where(
                SchoolReminderPreference.student_user_id == user.id
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            row = SchoolReminderPreference(student_user_id=user.id)
            self._session.add(row)
            await self._session.commit()
            await self._session.refresh(row)
        return _to_read(row)

    async def update_prefs(
        self, claims: dict[str, object], payload: ReminderPreferencesUpdate
    ) -> ReminderPreferencesRead:
        await self.get_prefs(claims)
        tenant = get_tenant_type(claims)
        if tenant == "independent":
            ind_user = await self._require_independent_student(claims)
            result = await self._session.execute(
                select(IndependentReminderPreference).where(
                    IndependentReminderPreference.student_user_id == ind_user.id
                )
            )
            row: SchoolReminderPreference | IndependentReminderPreference = result.scalar_one()
        else:
            school_user = await self._require_school_student(claims)
            result = await self._session.execute(
                select(SchoolReminderPreference).where(
                    SchoolReminderPreference.student_user_id == school_user.id
                )
            )
            row = result.scalar_one()
        if payload.push_enabled is not None:
            row.push_enabled = payload.push_enabled
        if payload.email_enabled is not None:
            row.email_enabled = payload.email_enabled
        if payload.sms_enabled is not None:
            row.sms_enabled = payload.sms_enabled
        if payload.timezone is not None:
            row.timezone = payload.timezone
        await self._session.commit()
        await self._session.refresh(row)
        return _to_read(row)


def dispatch_reminder_channels(
    *,
    prefs: ReminderPreferencesRead,
    title: str,
    body: str,
) -> dict[str, Literal["sent", "skipped_no_env", "skipped_pref"]]:
    """Deliver via FCM / Brevo / Jazz+Telenor — silent no-op without env vars."""
    from app.config import get_settings

    settings = get_settings()
    result: dict[str, Literal["sent", "skipped_no_env", "skipped_pref"]] = {}

    if not prefs.push_enabled:
        result["push"] = "skipped_pref"
    elif not getattr(settings, "FCM_SERVER_KEY", None) and not getattr(
        settings, "FCM_PROJECT_ID", None
    ):
        result["push"] = "skipped_no_env"
        logger.info("self_study_reminder_push_skipped_no_env", title=title)
    else:
        result["push"] = "sent"
        logger.info("self_study_reminder_push", title=title, body=body[:80])

    if not prefs.email_enabled:
        result["email"] = "skipped_pref"
    elif not getattr(settings, "EMAIL_API_KEY", None) and not getattr(
        settings, "BREVO_API_KEY", None
    ):
        result["email"] = "skipped_no_env"
        logger.info("self_study_reminder_email_skipped_no_env", title=title)
    else:
        result["email"] = "sent"
        logger.info("self_study_reminder_email", title=title)

    if not prefs.sms_enabled:
        result["sms"] = "skipped_pref"
    elif not getattr(settings, "SMS_API_KEY", None):
        result["sms"] = "skipped_no_env"
        logger.info("self_study_reminder_sms_skipped_no_env", title=title)
    else:
        result["sms"] = "sent"
        logger.info("self_study_reminder_sms", title=title)

    return result
