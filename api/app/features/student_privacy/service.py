"""#72 privacy helpers + service — T-162 (M-12).

``student_allows_teacher_share(user_id)`` is the shared filter for event
payloads, parent read paths, and future Flow 7 / Flow 10 consumers.
Missing settings rows default to share (Open Q12).
"""

from __future__ import annotations

from typing import Literal, cast

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, PermissionDeniedError
from app.core.tenant import get_tenant_type
from app.features.audit.actions import STUDENT_TEACHER_SHARE_TOGGLED
from app.features.student_mode.models import (
    DEFAULT_MODE_STATE,
    StudyMode,
    TeacherActivityShare,
    UserSettings,
)
from app.features.student_mode.repository import UserSettingsRepository
from app.features.student_onboarding.models import StudentProfile
from app.features.student_onboarding.repository import StudentProfileRepository
from app.features.student_privacy.schemas import (
    TeacherActivityShareRead,
    TeacherActivityShareUpdate,
)
from app.features.users.models import User, UserRole
from app.features.users.repository import UserRepository
from app.infrastructure.audit.log import audit

logger = structlog.get_logger(__name__)


async def student_allows_teacher_share(session: AsyncSession, user_id: str) -> bool:
    """Return True when the student's #72 preference allows teacher/parent share.

    No ``user_settings`` row ⇒ default share (Open Q12). Independent students
    have no #72 row; callers that reach here for school students get the default.
    """
    repo = UserSettingsRepository(session)
    settings = await repo.get_by_user_id(user_id)
    if settings is None:
        return True
    return settings.teacher_activity_share == TeacherActivityShare.SHARE


def _default_active_mode(profile: StudentProfile) -> StudyMode:
    if profile.lecture_mode_enabled:
        return StudyMode.LECTURE
    if profile.self_study_mode_enabled:
        return StudyMode.SELF_STUDY
    return StudyMode.LECTURE


class StudentPrivacyService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._settings_repo = UserSettingsRepository(session)
        self._profile_repo = StudentProfileRepository(session)
        self._user_repo = UserRepository(session)

    def _reject_independent(self, claims: dict[str, object]) -> None:
        """#72 is hidden for independent students (Flow 8 §3.12)."""
        if get_tenant_type(claims) == "independent" or str(claims.get("role", "")) == (
            "independent_student"
        ):
            raise NotFoundError("Teacher-share privacy is not available")

    async def _require_school_student(self, claims: dict[str, object]) -> User:
        self._reject_independent(claims)
        role = str(claims.get("role", ""))
        if role != UserRole.STUDENT.value:
            raise PermissionDeniedError("Requires a school student account")
        user = await self._user_repo.get_by_authentik_id(str(claims.get("sub", "")))
        if user is None or user.role != UserRole.STUDENT:
            raise NotFoundError("Student not found")
        return user

    async def _ensure_settings(self, user: User) -> UserSettings:
        existing = await self._settings_repo.get_by_user_id(user.id)
        if existing is not None:
            return existing
        profile = await self._profile_repo.get_by_user_id(user.id)
        active = _default_active_mode(profile) if profile is not None else StudyMode.LECTURE
        settings = UserSettings(
            user_id=user.id,
            active_mode=active,
            mode_state_jsonb=dict(DEFAULT_MODE_STATE),
            teacher_activity_share=TeacherActivityShare.SHARE,
        )
        return await self._settings_repo.create(settings)

    @staticmethod
    def _to_read(settings: UserSettings) -> TeacherActivityShareRead:
        return TeacherActivityShareRead(
            teacher_activity_share=cast(
                Literal["share", "private"], settings.teacher_activity_share.value
            )
        )

    async def get_teacher_share(self, claims: dict[str, object]) -> TeacherActivityShareRead:
        user = await self._require_school_student(claims)
        settings = await self._ensure_settings(user)
        return self._to_read(settings)

    async def set_teacher_share(
        self,
        payload: TeacherActivityShareUpdate,
        claims: dict[str, object],
        *,
        actor_id: str,
    ) -> TeacherActivityShareRead:
        user = await self._require_school_student(claims)
        settings = await self._ensure_settings(user)
        previous = settings.teacher_activity_share
        target = TeacherActivityShare(payload.teacher_activity_share)
        if previous == target:
            return self._to_read(settings)

        settings.teacher_activity_share = target
        settings = await self._settings_repo.update(settings)

        await audit(
            session=self._session,
            action=STUDENT_TEACHER_SHARE_TOGGLED,
            actor_id=actor_id,
            actor_role=str(claims.get("role", "")),
            target_type="user_settings",
            target_id=user.id,
            school_id=user.school_id,
            metadata={
                "teacher_activity_share": target.value,
                "previous": previous.value,
                "feature": "72",
            },
        )
        logger.info(
            "student_teacher_share_toggled",
            user_id=user.id,
            teacher_activity_share=target.value,
            previous=previous.value,
        )
        return self._to_read(settings)
