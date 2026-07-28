"""School student mode switcher service — T-101."""

from __future__ import annotations

from typing import Literal, cast

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, PermissionDeniedError, PreconditionFailedError
from app.core.tenant import get_tenant_type
from app.features.student_mode.events import publish_mode_changed
from app.features.student_mode.models import DEFAULT_MODE_STATE, StudyMode, UserSettings
from app.features.student_mode.repository import UserSettingsRepository
from app.features.student_mode.schemas import ModeStateBlob, StudentModeRead, StudentModeUpdate
from app.features.student_onboarding.models import StudentProfile
from app.features.student_onboarding.repository import StudentProfileRepository
from app.features.users.models import User, UserRole
from app.features.users.repository import UserRepository
from app.infrastructure.audit.log import audit

logger = structlog.get_logger(__name__)


def _as_mode_state(raw: dict[str, object] | None) -> ModeStateBlob:
    if not raw:
        return ModeStateBlob()
    lecture = raw.get("lecture")
    self_study = raw.get("self_study")
    return ModeStateBlob(
        lecture=dict(lecture) if isinstance(lecture, dict) else {},
        self_study=dict(self_study) if isinstance(self_study, dict) else {},
    )


def _default_active_mode(profile: StudentProfile) -> StudyMode:
    if profile.lecture_mode_enabled:
        return StudyMode.LECTURE
    if profile.self_study_mode_enabled:
        return StudyMode.SELF_STUDY
    return StudyMode.LECTURE


class StudentModeService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._settings_repo = UserSettingsRepository(session)
        self._profile_repo = StudentProfileRepository(session)
        self._user_repo = UserRepository(session)

    def _reject_independent(self, claims: dict[str, object]) -> None:
        """Independent students have no mode switcher — 404 (flow-4 §3.4 / §5.8)."""
        if get_tenant_type(claims) == "independent" or str(claims.get("role", "")) == (
            "independent_student"
        ):
            raise NotFoundError("Mode switcher is not available")

    async def _require_school_student(self, claims: dict[str, object]) -> User:
        self._reject_independent(claims)
        role = str(claims.get("role", ""))
        if role != UserRole.STUDENT.value:
            raise PermissionDeniedError("Requires a school student account")

        user = await self._user_repo.get_by_authentik_id(str(claims.get("sub", "")))
        if user is None or user.role != UserRole.STUDENT:
            raise NotFoundError("Student not found")
        return user

    async def _require_ready_profile(self, user_id: str) -> StudentProfile:
        profile = await self._profile_repo.get_by_user_id(user_id)
        if profile is None or not (profile.lecture_mode_enabled or profile.self_study_mode_enabled):
            raise PreconditionFailedError("Complete mode selection before switching modes")
        return profile

    def _to_read(self, settings: UserSettings, profile: StudentProfile) -> StudentModeRead:
        return StudentModeRead(
            active_mode=cast(Literal["lecture", "self_study"], settings.active_mode.value),
            mode_state=_as_mode_state(settings.mode_state_jsonb),
            lecture_mode_enabled=profile.lecture_mode_enabled,
            self_study_mode_enabled=profile.self_study_mode_enabled,
        )

    async def ensure_settings_for_onboarding(
        self,
        *,
        user_id: str,
        lecture_mode: bool,
        self_study_mode: bool,
    ) -> UserSettings:
        """Upsert user_settings when onboarding modes are first selected (T-078 → T-101)."""
        existing = await self._settings_repo.get_by_user_id(user_id)
        if existing is not None:
            return existing

        if lecture_mode:
            active = StudyMode.LECTURE
        elif self_study_mode:
            active = StudyMode.SELF_STUDY
        else:
            active = StudyMode.LECTURE

        settings = UserSettings(
            user_id=user_id,
            active_mode=active,
            mode_state_jsonb=dict(DEFAULT_MODE_STATE),
        )
        return await self._settings_repo.create(settings)

    async def get_mode(self, claims: dict[str, object]) -> StudentModeRead:
        user = await self._require_school_student(claims)
        profile = await self._require_ready_profile(user.id)
        settings = await self._settings_repo.get_by_user_id(user.id)
        if settings is None:
            settings = UserSettings(
                user_id=user.id,
                active_mode=_default_active_mode(profile),
                mode_state_jsonb=dict(DEFAULT_MODE_STATE),
            )
            settings = await self._settings_repo.create(settings)
        return self._to_read(settings, profile)

    async def set_mode(
        self,
        payload: StudentModeUpdate,
        claims: dict[str, object],
        actor_id: str,
    ) -> StudentModeRead:
        user = await self._require_school_student(claims)
        profile = await self._require_ready_profile(user.id)
        settings = await self._settings_repo.get_by_user_id(user.id)
        if settings is None:
            settings = UserSettings(
                user_id=user.id,
                active_mode=_default_active_mode(profile),
                mode_state_jsonb=dict(DEFAULT_MODE_STATE),
            )
            settings = await self._settings_repo.create(settings)

        previous = settings.active_mode
        target = StudyMode(payload.active_mode)

        # Enable the target mode on the profile if the student only opted into one at onboarding.
        if target == StudyMode.LECTURE and not profile.lecture_mode_enabled:
            profile.lecture_mode_enabled = True
            profile = await self._profile_repo.update(profile)
        elif target == StudyMode.SELF_STUDY and not profile.self_study_mode_enabled:
            profile.self_study_mode_enabled = True
            profile = await self._profile_repo.update(profile)

        state = _as_mode_state(settings.mode_state_jsonb)
        if payload.leaving_mode_state is not None and previous != target:
            if previous == StudyMode.LECTURE:
                state = ModeStateBlob(
                    lecture=dict(payload.leaving_mode_state),
                    self_study=state.self_study,
                )
            else:
                state = ModeStateBlob(
                    lecture=state.lecture,
                    self_study=dict(payload.leaving_mode_state),
                )

        settings.active_mode = target
        settings.mode_state_jsonb = state.model_dump()
        settings = await self._settings_repo.update(settings)

        await audit(
            session=self._session,
            action="student.mode_changed",
            actor_id=actor_id,
            target_type="user_settings",
            target_id=user.id,
            school_id=user.school_id,
            metadata={
                "active_mode": target.value,
                "previous_mode": previous.value if previous != target else None,
            },
        )
        await publish_mode_changed(
            user_id=user.id,
            school_id=user.school_id or "",
            active_mode=target.value,
            previous_mode=previous.value if previous != target else None,
        )
        logger.info(
            "student_mode_changed",
            user_id=user.id,
            active_mode=target.value,
            previous_mode=previous.value,
        )
        return self._to_read(settings, profile)
